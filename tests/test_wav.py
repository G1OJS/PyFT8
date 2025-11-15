import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio

wav_file = "210703_133430.wav"
#wav_file = '251114_135115.wav'

demod = FT8Demodulator()

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
    if(decode):
        decoded_candidates.append(c)
        print(decode['all_txt_line'], decode['decode_dict']['t0_idx'] , c.llr_std, c.bounds.t0_idx, c.bounds.f0_idx)

timers.timedLog("Start to Show spectrum")
wf = Waterfall(demod.spectrum, f1=3500)
wf.update_main()
timers.timedLog("Start to Show candidates")
from PyFT8.datagrids import Spectrum, Candidate
from PyFT8.signaldefs import FT8

#cands = [(18,282),(17,306),(13,346),(12,790),(7,1034),(17,1233)]
#decoded_candidates.append(Candidate(FT8, demod.spectrum, 17, 1233, 1000))
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)



