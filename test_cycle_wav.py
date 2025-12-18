
import numpy as np
from PyFT8.waterfall import Waterfall
import PyFT8.timers as timers
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
        heads = ['        Cycle', 'demap','ldpc','decode', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx', 'ncheck']
        print(''.join([f"{t:>8} " for t in heads]))
    dd = c.decode_dict
    vals = [f"{dd['cyclestart_str']} {c.demap_returned %15:8.2f} {c.ldpc_returned %15:8.2f} {timers.tnow() %15:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{dd['sync_score']:>5.2f}",  f"{dd['snr']:5.0f}", dd['t0_idx'], dd['f0_idx'], dd['ncheck_initial']]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)

wav_file = "210703_133430.wav"
#wav_file = "test_wav.wav"
start_load = timers.tnow()
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = wav_file, 
                          max_iters = 25,  max_ncheck = 38,
                          sync_score_thresh = 4, max_cycles = 5, return_candidate = True)

while cycle_manager.running:
    timers.sleep(0.5)
timers.sleep(2)

cycle_manager.output_timings()
unique_decoded_candidates = list(set(decoded_candidates))
print(f"DONE. {len(unique_decoded_candidates)} unique decodes.")

#wf = Waterfall(cycle_manager.spectrum)
#wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates)



