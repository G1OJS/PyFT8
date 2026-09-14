import numpy as np
import wave

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

SAMP_RATE = 12000
SYM_RATE = 6.25
N_SYMS = 79
T_CYC = 15
HPS = 4
BPT = 2

def read_wav(filename):
    wf = wave.open(filename, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    wf.close()
    return np.frombuffer(all_audio_frames, dtype=np.int16)

def get_tfgrid(audio_samples):
    fft_len = int(BPT * SAMP_RATE // SYM_RATE)
    fft_window = np.hanning(fft_len).astype(np.float32)
    nhops = int(T_CYC * SYM_RATE * HPS)
    nfreqs = int(BPT * 3000 / SYM_RATE)
    tfgrid = np.ones((nhops, nfreqs), dtype = np.float32)
    for hop in range(nhops):
        s0 = int(hop * SAMP_RATE / (SYM_RATE * HPS)) - fft_len
        s1 = s0 + fft_len
        if s0 > 0 and s1 < len(audio_samples):
            winaud = audio_samples[s0:s1] * fft_window
            z = np.fft.rfft(winaud)[:nfreqs]
            tfgrid[hop, :] = np.abs(z)
    return tfgrid


aud = read_wav('test_08.wav')
tfgrid = get_tfgrid(aud)

import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize = (12,5))
dB = 20 * np.log10(tfgrid)
dB = np.clip(dB, np.max(dB)-30, None)
im = ax.imshow(dB, origin = 'lower')


plt.show()




