import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio

wav_file = "210703_133430.wav"

demod = FT8Demodulator()
wf = Waterfall(demod.spectrum, f1=3500)

timers.timedLog(f"Start to Load audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
demod.spectrum.load_audio(audio_in)
timers.timedLog("Start to Find candidates")
candidates = demod.find_candidates()
timers.timedLog(f"Found {len(candidates)} candidates")
timers.timedLog("Start to deduplicate candidate frequencies")
candidates = demod.deduplicate_candidate_freqs(candidates)
timers.timedLog(f"Now have {len(candidates)} candidates")
timers.timedLog("Start to sync and demodulate candidates")

decoded_candidates = []
for i, c in enumerate(candidates):
    demod.sync_candidate(c)
    decode = demod.demodulate_candidate(c, cyclestart_str="test")
    import pickle as pkl
    if(decode):
        with open(f"cand_{int(c.bounds.f0)}.pkl","wb") as f:
            pkl.dump(c.complex_grid,f)
        decoded_candidates.append(c)
        print(decode['all_txt_line'], decode['decode_dict']['t0_idx'] , c.llr_std)

timers.timedLog("Start to Show spectrum")
wf.update_main()
timers.timedLog("Start to Show candidates")
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



