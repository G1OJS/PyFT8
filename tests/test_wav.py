import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config

decoded_candidates = []

def non_threaded_decode():
    cycle_manager.running = False
    n_cands = len(cycle_manager.cands_to_decode)
    print(f"n_cands = {n_cands}")
    for c in cycle_manager.cands_to_decode:
        cycle_manager.demod.demodulate_candidate(c, cycle_manager.onResult)

def threaded_decode():
    cycle_manager.running = True
    while(len(cycle_manager.cands_to_decode)>0):
        timers.sleep(0.1)
    cycle_manager.running = False

def onDecode(c):
    decoded_candidates.append(c)
    dd = c.decode_dict
    print(f"{dd['call_a']:>8} {dd['call_b']:>8} {dd['grid_rpt']:>8} {c.score:8.3f} {c.synced_pwr/1e9:8.3f} {c.snr:8.0f} "
      +f"{c.origin[0]:>8} {c.origin[1]:>8} {c.n_its:>8}")

wav_file = "210703_133430.wav"
#wav_file = "251115_135700.wav"

timers.timedLog(f"Loading audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
cycle_manager = Cycle_manager(onDecode, onOccupancy = None, verbose = True, audio_in = audio_in, 
                              sync_score_thresh = 1.5, min_sd = 0,
                              max_parallel_decodes = 50, max_candidate_lifetime = 1000)
heads = ['Rx call', 'Tx call', 'GrRp', 'SyncScr', 'SyncPwr', 'snr', 't0', 'f0', 'iters']
print(''.join([f"{t:>8} " for t in heads]))

non_threaded_decode()

print(f"DONE. Unique decodes = {len(decoded_candidates)}")

#wf = Waterfall(cycle_manager.spectrum)
#wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates)



