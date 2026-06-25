import numpy as np
from PyFT8.transmitter import AudioOut
from PyFT8.receiver import AudioIn

f_base = 100*6.25
audio_out = AudioOut()
wf = audio_out.create_ft8_wave([0,1,2,3,4,5,6,7,0,0,0,0,0,0,0,0,0,0], f_base = f_base)
audio_out.write_to_wave_file(wf,'tmp.wav')

audio_in = AudioIn(3000, ["tmp.wav"])
HPS, BPT = audio_in.oversample.values()
print(HPS, BPT)
audio_in.dBgrid_main_ptr = 0
audio_in.load_wavs(["tmp.wav"])
f0_idx = int(f_base / audio_in.df)
print(audio_in.df)
print(f0_idx)


import matplotlib.pyplot as plt
fig, ax = plt.subplots()
h0_idx = 0
ax.imshow(audio_in.dBgrid_main[h0_idx:h0_idx+8*HPS, f0_idx:f0_idx+8*BPT])
plt.show()


for i in range(30):
    print(' '.join([f"{v:6.0f}" for v in audio_in.dBgrid_main[i, f0_idx:f0_idx+8]]))
