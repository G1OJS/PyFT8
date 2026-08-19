import numpy as np
import wave
from PyFT8.decoders import ldpc_decode, osd_012, crc_unpack91

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

SAMP_RATE = 12000
SYM_RATE = 6.25
N_SYMS = 79
T_CYC = 15
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))

def dB_to_llr(payload_dB_grid):
    p = payload_dB_grid 
    snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
    print(snr)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    mean = np.mean(llr)
    var = np.mean(llr*llr) - mean*mean
    llr_sd = np.sqrt(var)
    llr = 2.83 * llr / llr_sd
    return llr

def get_candidate_tfgrid(cycle_spectrum, origin):
    fft1_len = len(cycle_spectrum)
    print(fft1_len)
    global candidate_spectrum, candidate_tf_zgrid

    # downsample to 32 samples per symbol / 200 samples per sec
    df = SAMP_RATE / fft1_len
    fb_0 = int(0.5 + origin['f0'] / df )
    candidate_spectrum[150:1000] = cycle_spectrum[fb_0:fb_0+850]
    candidate_spectrum[:150] = cycle_spectrum[fb_0-150:fb_0]
    candidate_spectrum[900:1000] *= 0.5*(1+np.cos(np.linspace(np.pi,0,100)))
    candidate_spectrum[:100] *= 0.5*(1+np.cos(np.linspace(-np.pi,0,100)))
    candidate_spectrum = np.roll(candidate_spectrum, -150)
    candidate_zsig = np.fft.ifft(candidate_spectrum)

    # get candidate symbol spectra x79 with df = 1 tone spacing
    dt = (1 / SAMP_RATE) * fft1_len / fft2_len
    symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
    start = int(origin['t0']/dt)
    idx = start + np.arange(N_SYMS)*32
    idx = np.clip(idx, 0, len(candidate_zsig)-32)
    symbols = np.empty((N_SYMS,32), dtype=np.complex64)
    for j, i0 in enumerate(idx):
        symbols[j,:] = candidate_zsig[i0:i0+32]
    candidate_tf_zgrid = np.fft.fft(symbols, axis=1)[:, :8]

    return candidate_tf_zgrid

fft2_len = 3200
candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
candidate_tf_zgrid = np.ones((N_SYMS, 8), dtype = np.complex64)
wav_file = 'test_09.wav'
# get full audio spectrum 
wf = wave.open(wav_file, "rb")
all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
wf.close()
fft1_len = 192000
samples = np.zeros(fft1_len)
samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
samples[:len(samps_in)] = samps_in 
all_audio_spectrum = np.fft.fft(samples)

import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize = (12,5))
origin = {'f0':1156, 't0':1.05}

candidate_tf_zgrid = get_candidate_tfgrid(all_audio_spectrum, origin)
dB = 20*np.log10(np.abs(candidate_tf_zgrid))
llr = dB_to_llr(dB[PAYLOAD_SYMB_IDXS,:])
res_osd = osd_012(llr, singleflips = 45, doubleflips = 25)
res_ldpc = ldpc_decode(llr, 900, 100)

print(f"{res_osd} {res_ldpc[0]}")

m = np.max(dB)
im = ax.imshow(dB, origin = 'lower', vmax = m-10, vmin = m-80)
im.set_data(dB)

plt.show()




