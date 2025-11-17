import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
#from PyFT8.datagrids import Spectrum, Candidate
#from PyFT8.signaldefs import FT8
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio

wav_file = "210703_133430.wav"
#wav_file = '251114_135115.wav'
wav_file = "251115_135700.wav"

demod = FT8Demodulator()

t_start_load = timers.tnow()
print("\n")
timers.timedLog(f"Loading audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
timers.timedLog(f"Finding candidates")
demod.load_audio(audio_in)
candidates = demod.find_candidates(silent = True)
timers.timedLog(f"Found {len(candidates)} candidates")
print("\n")

decoded_candidates = []
unique_decodes = set()
heads = ['Tload+', 'Rx call', 'Tx call', 'GrRp', 'SchScr%', 'SyncScr', 't0', 'hop', 'cfg', 'f0', 'sch_idx', 'sync_idx']
print(''.join([f"{t:>8} " for t in heads]))
for i, c in enumerate(candidates):
    decode = demod.demodulate_candidate(demod.spectrum, c, 'test', silent = True)
    if(decode):
        tdelta = timers.tnow() - t_start_load 
        decoded_candidates.append(c)
        dd = decode['decode_dict']
        msg = f"{dd['call_a']} {dd['call_b']} {dd['grid_rpt']}"
        if(msg in unique_decodes):
            dd.update({'call_a':'-', 'call_b':'-', 'grid_rpt':'-'})
        print(f"{tdelta:8.2f} {dd['call_a']:>8} {dd['call_b']:>8} {dd['grid_rpt']:>8} {c.score_init:8.0f} {c.score:8.0f} {c.bounds.t0_idx:>8} {c.iHop:>8} {c.iconf:>8} {c.bounds.f0_idx:>8} {c.sort_idx_finder:>8} {c.sort_idx_sync:>8}")
        unique_decodes.add(msg)
tdelta = timers.tnow() - t_start_load
print(f"{tdelta:8.2f} DONE. Unique decodes = {len(unique_decodes)}")

      
wf = Waterfall(demod.spectrum, f1=3500)
wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates)



