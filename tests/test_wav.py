import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
from PyFT8.comms_hub import config
from PyFT8.sigspecs import FT8
from PyFT8.rx.cycle_manager import Cycle_manager

decoded_candidates = set()


first = True
def onDecode(c):
    global first
    global cycle_manager
    if(first):
        heads = ['End_cyc+', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'LLR_sd', 'snr', 't0_idx', 'f0_idx',  'iters']
        print(''.join([f"{t:>8} " for t in heads]))
        first = False
    decoded_candidates.add(c)
    dd = c.decode_result
    t_decode = timers.tnow()-cycle_manager.wav_file_start_time - 15
    vals = [f"{t_decode:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{c.sync_result['sync_score']:>5.2f}", f"{c.demap_result['llr_sd']:5.2f}", f"{c.demap_result['snr']:5.0f}",
            c.sync_result['origin'][0], c.sync_result['origin'][1], c.ldpc_result['n_its'] ]
    print(''.join([f"{t:>8} " for t in vals]))

wav_file = "210703_133430.wav"
#wav_file = "251115_135700.wav"
start_load = timers.tnow()
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = wav_file, 
                          max_iters = 60, max_stall = 8, max_ncheck = 40,
                          sync_score_thresh = 2.3, cycles = 1)

while cycle_manager.running:
    timers.sleep(0.5)
    
print(f"DONE. Unique decodes = {len(decoded_candidates)}")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



