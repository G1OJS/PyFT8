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
fft_len = int(BPT * SAMP_RATE // SYM_RATE)
df = SYM_RATE / BPT

def read_wav(filename):
    wf = wave.open(filename, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    wf.close()
    return np.frombuffer(all_audio_frames, dtype=np.int16)

def get_tfgrid(audio_samples):
    
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

def get_data(file_number):
    wav_folder = r"C:\Users\drala\Documents\Projects\GitHub\ft8_lib\test\wav\20m_busy"
    data_folder = './data'
    with open(f"{data_folder}/wsjtx_decodes_{file_number:02d}.txt",'r') as f:
        decs = f.readlines()
    fdecs =[]
    for d in decs:
        fdecs.append(float(d.split()[6]))
        
    aud = read_wav(f"{wav_folder}/test_{file_number:02d}.wav")
    tfgrid = get_tfgrid(aud)

    return tfgrid, fdecs

def get_f_costas1(tfgrid):
    COSTAS = [3,1,4,0,6,5,2]
    test = np.ones_like(tfgrid)
    for i, t in enumerate(COSTAS):
        test *=  np.roll(np.roll(tfgrid, -t * BPT, axis = 1),  -i*HPS, axis = 0)
        test /= np.max(test)
    test_grid = np.log10(test)
    test = np.max(test_grid, axis = 0)
    return test, test_grid


import matplotlib.pyplot as plt
fig, axs = plt.subplots(3,1, figsize = (12,5), sharex = 'all', layout='constrained')


tfgrid, fdecs = get_data(8)
costas1, costas1_grid = get_f_costas1(tfgrid)
nfreqs = tfgrid.shape[1]
freqs = 3.125 * np.arange(nfreqs)

dB = 20 * np.log10(tfgrid)
im = axs[0].imshow(dB, origin = 'lower', extent = [0,freqs[-1], 0, 15*4/0.16])

im = axs[1].imshow(costas1_grid, origin = 'lower', extent = [0, freqs[-1], 0, 15*4/0.16])

axs[2].plot(freqs, costas1)
axs[2].set_xlim(0,freqs[-1])
for f in fdecs:
    axs[2].axvline(f)

plt.show()




