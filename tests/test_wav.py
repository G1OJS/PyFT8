import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
from scipy.io import wavfile
import PyFT8.timers as timers
# --- Load a known FT8 WAV file ---
sr, audio = wavfile.read("210703_133430.wav")
audio = audio.astype(np.float32)
if audio.ndim > 1:
    audio = np.mean(audio, axis=1)  # ensure mono

demod = FT8Demodulator(sample_rate=sr, fbins_pertone=3, hops_persymb=3)
wf = Waterfall(demod.spectrum, f1=3500)

timers.timedLog("Start to Load audio")
demod.spectrum.feed_audio(audio)

timers.timedLog("Start to Show spectrum")
wf.update_main()

timers.timedLog("Start to Find candidates")
candidates = demod.find_candidates(100,3300, topN=500)
timers.timedLog(f"Found {len(candidates)} candidates")
timers.timedLog("Start to deduplicate candidate frequencies")
candidates = demod.deduplicate_candidate_freqs(candidates, topN=100)
timers.timedLog(f"Now have {len(candidates)} candidates")
timers.timedLog("Start to sync candidates")
candidates = demod.sync_candidates(candidates, topN=30)
timers.timedLog(f"Synced {len(candidates)} candidates")

timers.timedLog("Start to Show candidates")
wf.update_main(candidates=candidates)
#wf.show_zoom(candidates=candidates[:5])

timers.timedLog("Start to Demodulate")
decodes = demod.demodulate(candidates, cyclestart_str="TEST")
timers.timedLog(f"Decoded {len(decodes)} signals")

for d in decodes:
    bounds = d[0]['bounds']
    print(d[1], bounds.t0_idx, bounds.f0_idx )
