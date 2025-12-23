WAV =  "210703_133430.wav"

import numpy as np
import time
from PyFT8.waterfall import Waterfall
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = []
unique_decodes = set()
first = True

def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['        Cycle', 't_demap','t_ldpc', 't_osd', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx', 'ncheck', 'n_its']
        print(''.join([f"{t:>8} " for t in heads]))
    def t_fmt(t):return f"{t %15:8.2f}" if t else f"{'-':>8}"
    vals = [f"{c.cyclestart_str} {t_fmt(c.pipeline.demap.completed_time)} {t_fmt(c.pipeline.ldpc.completed_time)} {t_fmt(c.pipeline.osd.completed_time)}",
            c.call_a, c.call_b, c.grid_rpt,
            f"{c.pipeline.sync.result.score:>5.2f}",  f"{c.snr:5.0f}", c.h0_idx, c.f0_idx, c.pipeline.ldpc.metrics.ncheck_initial, c.pipeline.ldpc.metrics.n_its]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)
    unique_decodes.add(c.call_a + c.call_b + c.grid_rpt,)

cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = WAV, 
                          max_iters = 25,  max_ncheck = 38, verbose = True,
                          sync_score_thresh = 3.8, max_cycles = 2)

while cycle_manager.running:
    time.sleep(0.5)
time.sleep(2)

print(f"DONE. {len(unique_decodes)} unique decodes.")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



