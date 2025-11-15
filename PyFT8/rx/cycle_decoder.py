import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.datagrids import Candidate
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
global audio_in
audio_in = None

def start_cycle_decoder(onStart = None, onDecode = None, onOccupancy = None, onFinished = None):
    threading.Thread(target=cycle_decoder, kwargs=({'onStart':onStart, 'onDecode':onDecode, 'onOccupancy':onOccupancy, 'onFinished':onFinished})).start()

def log_decode(decode):
    timers.timedLog("No callback specified, logging: {decode}", logfile = "default_decodes.log", silent = True)

def cycle_decoder(onStart = None, onOccupancy = None, onDecode = log_decode, onFinished = None, topN = 500, score_thresh = 1000000, cycle_len = 15):
    global audio_in
    MAX_START_OFFSET_SECONDS = 0.5
    END_RECORD_GAP_SECONDS = 1

    timers.CYCLE_LENGTH = cycle_len
    while True:
        t_elapsed, t_remain, = timers.time_in_cycle()
        timers.sleep(t_remain)
        if(t_elapsed <5 and t_elapsed > MAX_START_OFFSET_SECONDS):
            timers.timedLog(f"Arrived to start recording at {t_elapsed} into cycle, waiting for next", silent = True)
        timers.timedLog("Cyclic demodulator requesting audio", silent = True)
        audio_in = audio.read_from_soundcard(timers.CYCLE_LENGTH - END_RECORD_GAP_SECONDS)
        threading.Thread(target=get_decodes, kwargs=({'onStart':onStart, 'onDecode':onDecode, 'onOccupancy':onOccupancy, 'onFinished':onFinished, 'topN':topN, 'score_thresh':score_thresh})).start()
        timers.timedLog("Cyclic demodulator passed audio for demodulating", silent = True)

def get_decodes(onStart=None, onDecode=None, onOccupancy=None, onFinished=None, topN=None, score_thresh=None):
    demod = FT8Demodulator(hops_persymb = 5)
    cyclestart_str = timers.cyclestart_str(0)
    demod.spectrum.load_audio(audio_in)
    all_messages = set()

    # decode the Rx freq first
    timers.timedLog("[Cycle decoder] Get Rx freq decode")
    f0_idx = int(config.rxfreq / demod.spectrum.df)
    rx_freq_candidate = Candidate(demod.sigspec, demod.spectrum, 0, f0_idx, -50)
    decode = demod.demodulate_candidate(rx_freq_candidate, cyclestart_str = cyclestart_str)
    timers.timedLog("[Cycle decoder] Rx freq decoding done")
    if(onStart):
        onStart()
    if(decode):
        all_messages.add(decode['decode_dict']['message'] )
        decode['decode_dict'].update({'rxfreq': True})
    if(onDecode):
        onDecode(decode)
        
    
    all_messages.add(decode)
    candidates = demod.find_candidates(score_thresh = score_thresh, topN = topN)
    if(onOccupancy):
        occupancy, clear_freq = make_occupancy_array(candidates)
        onOccupancy(occupancy, clear_freq)
    for c in candidates:
        decode = demod.demodulate_candidate(c, cyclestart_str)
        if(decode):
            if(onDecode and decode['decode_dict']['message'] not in all_messages):
                all_messages.add(decode['decode_dict']['message'] )
                onDecode(decode)
    timers.timedLog("[Cycle decoder] all decoding done")
    if(onFinished):
        onFinished()

def make_occupancy_array(candidates, f0=0, f1=3500, bin_hz=10):
    occupancy = np.arange(f0, f1 + bin_hz, bin_hz)
    for c in candidates:
        occupancy[int((c.bounds.f0-f0)/bin_hz)] += c.score
    occupancy = occupancy/np.max(occupancy)
    fs0, fs1 = 1000,1500
    bin0 = int((fs0-f0)/bin_hz)
    bin1 = int((fs1-f0)/bin_hz)
    clear_freq = fs0 + bin_hz*np.argmin(occupancy[bin0:bin1])
    occupancy = 10*np.log10(occupancy + 1e-12)
    occupancy = 1 + np.clip(occupancy, -40, 0) / 40
    return occupancy, clear_freq
