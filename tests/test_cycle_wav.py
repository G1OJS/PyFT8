WAV =  "210703_133430.wav"

import numpy as np
import time
from PyFT8.waterfall import Waterfall
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = []
first = True

def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['        Cycle', 'demap','ldpc','decode', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx', 'ncheck', 'n_its']
        print(''.join([f"{t:>8} " for t in heads]))
    dd = c.decode_dict
    vals = [f"{dd['cyclestart_str']} {c.demap_returned %15:8.2f} {c.ldpc_returned %15:8.2f} {time.time() %15:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{dd['sync_score']:>5.2f}",  f"{dd['snr']:5.0f}", dd['t0_idx'], dd['f0_idx'], dd['ncheck_initial'], dd['n_its']]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)

print("Waiting for cycle rollover")
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = WAV, 
                          max_iters = 25,  max_ncheck = 38, verbose = True,
                          sync_score_thresh = 4, max_cycles = 2, return_candidate = True)

while cycle_manager.running:
    time.sleep(0.5)
time.sleep(2)

unique_decoded_candidates = list(set(decoded_candidates))
print(f"DONE. {len(unique_decoded_candidates)} unique decodes.")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



