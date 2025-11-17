import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.datagrids import Candidate
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall

global demod, duplicate_filter, onDecode, onOccupancy, topN, score_thresh, cycle_len
cycle_len = 15
duplicate_filter = set()

def start_cycle_decoder(onDecode1, onOccupancy1, score_thresh1):
    global onDecode, onOccupancy, score_thresh, topN
    topN = None
    onDecode, onOccupancy, score_thresh = onDecode1, onOccupancy1, score_thresh1
    threading.Thread(target=cycle_decoder).start()

def cycle_decoder():
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
        timers.timedLog("Cyclic demodulator passed audio for demodulating", silent = True)
        threading.Thread(target=_get_decodes, kwargs=({'audio_in':audio_in})).start()
    
def _get_decodes(audio_in):
    global demod, duplicate_filter
    demod = FT8Demodulator(hops_persymb = 5)
    cyclestart_str = timers.cyclestart_str(0)
    demod.load_audio(audio_in)
    duplicate_filter = set()

    # decode the Rx freq first
    if(onDecode):
        timers.timedLog("[Cycle decoder] Get Rx freq decode")
        f0_idx = int(config.rxfreq / demod.spectrum.df)
        rx_freq_candidate = Candidate(demod.sigspec, demod.spectrum, 0, f0_idx, -50, cyclestart_str)
        decode = demod.demodulate_candidate(demod.spectrum, rx_freq_candidate)
        timers.timedLog("[Cycle decoder] Rx freq decoding done")
        if(decode):
            duplicate_filter.add(decode['decode_dict']['message'] )
            decode['decode_dict'].update({'rxfreq': True})
            if(onDecode):
                onDecode(decode)
            
    candidates = demod.find_candidates(score_thresh = score_thresh, topN = topN)
    if(onOccupancy):
        occupancy, clear_freq = make_occupancy_array(candidates)
        onOccupancy(occupancy, clear_freq)

    if(onDecode):
        for c in candidates:
            threading.Thread(target=decode_candidate, kwargs = ({'spectrum':demod.spectrum,'c':c,'cyclestart_str':cyclestart_str})).start()

def decode_candidate(c):
    global duplicate_filter
    decode = demod.demodulate_candidate(c)
    if(decode):
        decode_dict = decode['decode_dict']
        key = f"{decode_dict['call_a']}{decode_dict['call_b']}"
        if(not key in duplicate_filter):
            duplicate_filter.add(key)
            onDecode(decode)

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
