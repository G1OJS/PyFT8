import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config

decoded_candidates = []
def onDecode(candidate):
    decoded_candidates.append(candidate)

wav_file = "210703_133430.wav"
#wav_file = '251114_135115.wav'
wav_file = "251115_135700.wav"

timers.timedLog(f"Loading audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
cycle_manager = Cycle_manager(onDecode, None, audio_in = audio_in, sync_score_thresh=2.5, iteration_sleep=0, verbose = False)
while(len(cycle_manager.cands_to_decode) > 0):
    timers.sleep(0.1)
cycle_manager.running = False
heads = ['Rx call', 'Tx call', 'GrRp', 'SyncScr', 'SyncPwr', 'snr', 't0', 'cfg', 'f0', 'sch_idx', 'iters']
print(''.join([f"{t:>8} " for t in heads]))
for c in decoded_candidates:
    dd = c.decode_dict
    print(f"{dd['call_a']:>8} {dd['call_b']:>8} {dd['grid_rpt']:>8} {c.score:8.3f} {c.synced_pwr/1e9:8.3f} {c.snr:8.0f} "
      +f"{c.origin[0]:>8} {c.iconf:>8} {c.origin[1]:>8} {c.n_its:>8}")
print(f"DONE. Unique decodes = {len(decoded_candidates)}")

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



