import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.signaldefs import FT8

decoded_candidates = []

def threaded_decode(audio_in):
    from PyFT8.rx.cycle_manager import Cycle_manager
    global audio_loaded_at

    cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, verbose = True, audio_in = audio_in, 
                              max_iters = 60, max_stall = 8, max_ncheck = 33,
                              sync_score_thresh = 2.3, llr_sd_thresh = 1.8)

    while len(cycle_manager.cands_list) == 0:
        timers.sleep(0.1)
    while len(cycle_manager.cands_list) > 0:
        timers.sleep(0.1)
    cycle_manager.running = False

def onDecode(c):
    decoded_candidates.append(c)
    dd = c.decode_result
    t_after_load = timers.tnow()-audio_loaded_at
    print(f"{t_after_load:5.2f} {dd['call_a']} {dd['call_b']} {dd['call_b']} {dd['grid_rpt']} {c.sync_result['sync_score']:5.2f}, {c.demap_result['snr']:5.0f}, {c.sync_result['origin']}, {c.ldpc_result['n_its']:5.0f}")

wav_file = "210703_133430.wav"
#wav_file = "251115_135700.wav"

timers.timedLog(f"Loading audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
audio_loaded_at = timers.tnow()
heads = ['Tload+', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'LLR_sd', 'snr', 't0_idx', 'f0_idx', 't0_s', 'f0_Hz',  'iters']
print(''.join([f"{t:>8} " for t in heads]))

#non_threaded_decode(audio_in)

threaded_decode(audio_in)

print(f"DONE. Unique decodes = {len(decoded_candidates)}")

#wf = Waterfall(cycle_manager.spectrum)
#wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates)



