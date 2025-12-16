
import numpy as np
from PyFT8.waterfall import Waterfall
import PyFT8.timers as timers
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = set()
first = True
def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['End_cyc+', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx']
        print(''.join([f"{t:>8} " for t in heads]))
    dd = c.decode_dict
    t_decode = (timers.tnow()+7) % 15 -7
    vals = [f"{t_decode:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{dd['sync_score']:>5.2f}",  f"{dd['snr']:5.0f}",
            dd['t0_idx'], dd['f0_idx']]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.add(c)




wav_file = "210703_133430.wav"
#wav_file = "test_wav.wav"
start_load = timers.tnow()
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = wav_file, 
                          max_iters = 50,  max_ncheck = 50,
                          sync_score_thresh = 3, max_cycles = 1, return_candidate = True)

while cycle_manager.running:
    timers.sleep(0.5)

cycle_manager.output_timings()
decoded_candidates = list(decoded_candidates)

print(f"DONE. {len(decoded_candidates)} unique decodes.")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



