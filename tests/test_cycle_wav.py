WAV =  "210703_133430.wav"

import numpy as np
import time
from PyFT8.waterfall import Waterfall
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = []
unique_decode_set = set()
unique_decodes = []
first = True

def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['        Cycle', 'Rx call', 'Tx call', 'GrRp',  'snr', 't0_idx', 'f0_idx', 'info']
        print(''.join([f"{t:>8} " for t in heads]))
    def t_fmt(t):return f"{t %15:8.2f}" if t else f"{'-':>8}"
    vals = [f"{c.cyclestart_str} ", c.call_a, c.call_b, c.grid_rpt,f"{c.snr:5.0f}", c.h0_idx, c.f0_idx]
    print(''.join([f"{t:>8} " for t in vals]), c.info_str)
    decoded_candidates.append(c)
    if not c.msg in unique_decode_set:
        unique_decode_set.add(c.msg)
        unique_decodes.append(c)

cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None,
                          audio_in_wav = WAV,  verbose = True,
                          max_cycles = 1)

while cycle_manager.running:
    time.sleep(0.5)
time.sleep(2)

print(f"DONE. {len(unique_decodes)} unique decodes.")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates = cycle_manager.cands_list + unique_decodes)
wf.show_zoom(candidates=unique_decodes)



