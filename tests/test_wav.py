import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio

wav_file = "210703_133430.wav"

demod = FT8Demodulator(sample_rate=12000, fbins_pertone=3, hops_persymb=3)
wf = Waterfall(demod.spectrum, f1=3500)

timers.timedLog(f"Start to Load audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
demod.spectrum.load_audio(audio_in)
timers.timedLog("Start to Find candidates")
candidates = demod.find_candidates(100,3400)
timers.timedLog(f"Found {len(candidates)} candidates")
timers.timedLog("Start to deduplicate candidate frequencies")
candidates = demod.deduplicate_candidate_freqs(candidates)
timers.timedLog(f"Now have {len(candidates)} candidates")
timers.timedLog("Start to sync and demodulate candidates")
decoded_candidates = []
for c in candidates:
    demod.sync_candidate(c)
    decode = demod.demodulate_candidate(c, cyclestart_str="test")
    if(decode):
        decoded_candidates.append(c)
        print(decode['all_txt_line'], decode['decode_dict']['t0_idx'] )

timers.timedLog("Start to Show spectrum")
wf.update_main()
timers.timedLog("Start to Show candidates")
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)


