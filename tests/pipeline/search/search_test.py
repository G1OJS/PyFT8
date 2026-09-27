import numpy as np
import wave, time

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
print(df)

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
            tfgrid[hop, :] = z
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
    t0 = time.time()
    COSTAS = [3,1,4,0,6,5,2]
    costas_product = np.ones_like(tfgrid)
    for i, t in enumerate(COSTAS):
        costas_product *=  np.roll(np.roll(tfgrid, -t * BPT, axis = 1),  -i*HPS, axis = 0)
        costas_product /= np.max(np.abs(costas_product))
    costas_product[:7*HPS, :] = 0
    costas_product = np.abs(costas_product)
   # costas_product = costas_product / (1e-12 + 0.5*np.roll(costas_product, 0, -1) + 0.5*np.roll(costas_product, 0, 1))
    hops = np.argmax(costas_product, axis = 0) % (36 * HPS)
    return hops, costas_product, time.time() - t0


import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize = (12,5), layout='constrained')

tfgrid, fdecs = get_data(8)
tfgrid = tfgrid[:125, :]

hops, costas_product, time_taken = get_f_costas1(tfgrid)
print(time_taken)
nfreqs = tfgrid.shape[1]
freqs = df * np.arange(nfreqs)
dec_idxs = [int(f/df) for f in fdecs]

dB = 20 * np.log10(np.abs(tfgrid))
im = ax.imshow(dB, origin = 'lower', extent = [0,freqs[-1], 0, (1/3)*15*4/0.16])
ax.set_xlim(0,freqs[-1])

peaks = [(hops[i], freqs[i], costas_product[hops[i], i]) for i in range(len(freqs))]
peaks.sort(key = lambda pk: pk[2], reverse = True)
for i in range(50):
    print(peaks[i])
    ax.scatter(peaks[i][1], peaks[i][0], color = 'white')

plt.show()




