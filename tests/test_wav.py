import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers

wav_file = "210703_133430.wav"

demod = FT8Demodulator()
wf = Waterfall(demod.spectrum, f1=3500)
timers.timedLog(f"Start to Load audio from {wav_file}")
demod.spectrum.get_audio(wav_file)
timers.timedLog("Start to Show spectrum")
wf.update_main()
candidates, decodes = demod.demodulate_all(cyclestart_str = "Test")
timers.timedLog("Start to Show candidates")
wf.update_main(candidates=candidates)
wf.show_zoom(candidates=candidates)
timers.timedLog(f"Decodes: {len(decodes)}")

for d in decodes:
    if(d): print(d['all_txt'], d['decode_dict']['t0_idx'] )
