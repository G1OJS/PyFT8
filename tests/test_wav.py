import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
from PyFT8.rx.FT8_decoder import FT8_decode   # existing decoder
from scipy.io import wavfile

# --- Load a known FT8 WAV file ---
sr, audio = wavfile.read("210703_133430.wav")
audio = audio.astype(np.float32)
if audio.ndim > 1:
    audio = np.mean(audio, axis=1)  # ensure mono

# --- Init demodulator and spectrum ---
demod = FT8Demodulator(sample_rate=sr)
demod.feed_audio(audio)

# --- Optional visualisation ---
#wf = Waterfall(demod.spectrum, f1=4000)
#wf.update_main()  # initial spectrum display

# --- Find candidates ---
candidates = demod.find_candidates()
print(f"Found {len(candidates)} candidates")

# --- Draw candidate boxes on waterfall ---
#wf.update_main(candidates=candidates)

# --- Demodulate each candidate ---
#decodes = demod.demodulate(candidates, cyclestart_str="TEST")
#print(f"Decoded {len(decodes)} signals\n")

# --- Show results ---
#for d in decodes:
#    print(d["info"], "→", d["msg"])
