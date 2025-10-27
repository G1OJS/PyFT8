import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
from scipy.io import wavfile

# --- Load a known FT8 WAV file ---
sr, audio = wavfile.read("210703_133430.wav")
audio = audio.astype(np.float32)
if audio.ndim > 1:
    audio = np.mean(audio, axis=1)  # ensure mono

# --- Init demodulator and spectrum ---
demod = FT8Demodulator(sample_rate=sr, fbins_pertone=3, hops_persymb=3)
demod.spectrum.feed_audio(audio)

# --- Optional visualisation ---
wf = Waterfall(demod.spectrum, f1=4000)
wf.update_main()  # initial spectrum display

# --- Find candidates ---
candidates = demod.find_candidates(topN=25)
print(f"Found {len(candidates)} candidates")

# --- Draw candidate boxes on waterfall ---
wf.update_main(candidates=candidates)
#wf.show_zoom(candidates=candidates[:5])

# --- Demodulate each candidate ---
print("Demodulating")
decodes = demod.demodulate(candidates, cyclestart_str="TEST")
print(f"Decoded {len(decodes)} signals\n")

# --- Show results ---
for d in decodes:
    print(d[1])
