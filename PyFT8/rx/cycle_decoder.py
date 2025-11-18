import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.datagrids import Candidate
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall

def start_cycle_decoder(onDecode, onOccupancy, prioritise_rxfreq = True):
    threading.Thread(target=cycle_decoder, kwargs=({'onDecode':onDecode, 'onOccupancy':onOccupancy,'prioritise_rxfreq':prioritise_rxfreq})).start()

def cycle_decoder(onDecode, onOccupancy, prioritise_rxfreq):
    global audio_in
    timers.CYCLE_LENGTH = 15
    END_RECORD_GAP_SECONDS = 0.5

    while True:
        t_elapsed, t_remain, = timers.time_in_cycle()
        if(t_remain <14):
            timers.timedLog(f"[Cycle decoder] waiting {t_remain:.2f}s for cycle start", silent = False)
            timers.sleep(t_remain)
        audio_in = audio.read_from_soundcard(timers.CYCLE_LENGTH - END_RECORD_GAP_SECONDS)
        timers.timedLog("Cyclic demodulator passed audio for demodulating", silent = True)
        threading.Thread(target=_get_decodes, kwargs=({'audio_in':audio_in, 'onDecode':onDecode, 'onOccupancy':onOccupancy , 'prioritise_rxfreq':prioritise_rxfreq})).start()
    
def _get_decodes(audio_in, onDecode, onOccupancy, prioritise_rxfreq ):
    demod = FT8Demodulator()
    cyclestart_str = timers.cyclestart_str(0)
    demod.load_audio(audio_in)
   
    # decode the Rx freq first
    if(onDecode and prioritise_rxfreq):
        timers.timedLog("[Cycle decoder] Get Rx freq decode")
        f0_idx = int(config.rxfreq / demod.spectrum.df)
        rx_freq_candidate = Candidate(demod.spectrum, f0_idx, demod.candidate_size, cyclestart_str)
        decode = demod.demodulate_candidate(rx_freq_candidate)
        timers.timedLog("[Cycle decoder] Rx freq decoding done")
        if(decode):
            demod.duplicate_filter.add(decode['decode_dict']['message'] )
            decode['decode_dict'].update({'rxfreq': True})
            if(onDecode):
                onDecode(decode)
            
    candidates = demod.find_candidates(cyclestart_str)
    if(onOccupancy):
        occupancy, clear_freq = make_occupancy_array(candidates)
        onOccupancy(occupancy, clear_freq)

    if(onDecode):
        for c in candidates:
            #decode_candidate(demod, c, onDecode)
            threading.Thread(target=decode_candidate, kwargs = ({'demod':demod, 'c':c, 'onDecode':onDecode})).start()

def decode_candidate(demod, c, onDecode):
    decode = demod.demodulate_candidate(c, silent = False)
    if(decode):
        decode_dict = decode['decode_dict']
        key = f"{decode_dict['call_a']}{decode_dict['call_b']}"
        timers.timedLog(f"[cycle decoder] Received decode: {key}", silent = False)         
        if(not key in demod.duplicate_filter):
            demod.duplicate_filter.add(key)
            onDecode(decode)

def make_occupancy_array(candidates, f0=0, f1=3500, bin_hz=10):
    occupancy = np.arange(f0, f1 + bin_hz, bin_hz)
    for c in candidates:
        bin0 = int((c.origin_physical[1]-f0)/bin_hz)
        #binN = bin0 + int(c.sigspec.bw_Hz/bin_hz)
        occupancy[bin0] += c.score
    occupancy = occupancy/np.max(occupancy)
    fs0, fs1 = 1000,1500
    bin0 = int((fs0-f0)/bin_hz)
    bin1 = int((fs1-f0)/bin_hz)
    clear_freq = fs0 + bin_hz*np.argmin(occupancy[bin0:bin1])
    occupancy = 10*np.log10(occupancy + 1e-12)
    occupancy = 1 + np.clip(occupancy, -40, 0) / 40
    return occupancy, clear_freq
