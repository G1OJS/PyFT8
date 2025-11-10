import wave
import numpy as np

filename = '210703_133430.wav'
with wave.open(filename, 'rb') as wav:
    audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    
nFFT = 1920
spec = np.zeros((int(nFFT/2)+1))
samp_idx = 0

while True:
    if(samp_idx +nFFT > len(audio)): break
    specslice = np.fft.rfft(audio[samp_idx :samp_idx  + nFFT] * np.kaiser(nFFT,14))
    spec = np.vstack([spec, specslice])
    samp_idx  += 1920

f0_idx = 345
t0_idx = 4
cspec = spec[t0_idx:t0_idx+79, f0_idx:f0_idx + 8]
ngrp = 2
n_tns = 8
n_corrs = n_tns**ngrp
n_blocks = int(79/ngrp)
normgrid = np.zeros_like(cspec)
for symb_idx in range(0,ngrp*n_blocks):
    norm = cspec[symb_idx, np.argmax(np.abs(cspec[symb_idx,:]))]
    normgrid[symb_idx,:] = cspec[symb_idx,:]/norm
        
import matplotlib.pyplot as plt
fig, axs = plt.subplots(1,3)

axs[0].imshow(np.abs(cspec)**2, aspect = 0.5)
axs[1].imshow(np.real(normgrid), aspect = 0.5)

plt.show()



