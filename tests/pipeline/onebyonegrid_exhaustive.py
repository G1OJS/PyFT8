#!/usr/bin/env python3

import os, sys
import numpy as np
import wave

NSUBHOPS =4
NSUBFREQS=2
SYM_RATE =6.25
SAMP_RATE=12000
T_CYC=15
LDPC_CONTROL = (50, 15) 
H0_RANGE = [0, 20]
SYMBOL_IDXS = np.array( list(range(7, 36)) + list(range(43, 72)))
COSTAS = [3,1,4,0,6,5,2]
SYMBOLS_PER_CYCLE = int(T_CYC * SYM_RATE)

from PyFT8.receiver import unpack, LdpcDecoder, check_crc
wav_file = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy/test_01.wav"

print("start")
fft_len = int(SAMP_RATE // SYM_RATE)
fft_out_len = fft_len // 2 + 1
max_freq = 2750
df = SAMP_RATE / fft_len 
nFreqs = int(max_freq/df)
fft_window = fft_window=np.kaiser(fft_len,6).astype(np.float32)
dBgrid_main = np.ones((NSUBHOPS, NSUBFREQS, SYMBOLS_PER_CYCLE, nFreqs), dtype = np.float32) 
for subfreq in range(NSUBFREQS):
    for subhop in range(NSUBHOPS):
        dBgrid_main_ptr = 0
        wf = wave.open(wav_file, "rb")
        frames_discard = wf.readframes(int(fft_len * subhop / NSUBHOPS))
        frames = wf.readframes(fft_len)
        phase = np.exp(1j * np.linspace(0,-np.pi*2*subfreq/NSUBFREQS, fft_len))
        while frames:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.complex64)
            if len(samples) == fft_len:
                np.multiply(samples, fft_window, out=samples)
                np.multiply(samples, phase, out=samples)
                z = np.fft.fft(samples)[:nFreqs]
                dBgrid_main[subhop, subfreq, dBgrid_main_ptr, :] = 10*np.log10(z.real*z.real + z.imag*z.imag + 1e-12)
                dBgrid_main_ptr +=1
            frames = wf.readframes(fft_len)
        wf.close()

messages = {}

for fb in range(int(340/df), nFreqs - 8):
    #print(fb * df)
    freq_idxs = fb + np.array(range(8))
    score = 0
    msg = None
    for subfreq in range(NSUBFREQS):
        for h0_idx in range(H0_RANGE[0], H0_RANGE[1]):
            hops = h0_idx + SYMBOL_IDXS
            if msg is None:
                for subhop in range(NSUBHOPS):
                    p = dBgrid_main[np.ix_([subhop], [subfreq], hops, freq_idxs)][0,0,:,:]
                    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
                    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
                    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
                    llr = np.column_stack((llra, llrb, llrc)).ravel()
                    llr = np.clip(3.5 * llr / np.std(llr), -3.7, 3.7)
                    ldpc = LdpcDecoder()
                    ncheck = ldpc.calc_ncheck(llr)
                    if 0 < ncheck <= LDPC_CONTROL[0]:
                        llr, ncheck, nits = ldpc.decode(llr)
                    if ncheck == 0:
                        bits91_int = 0
                        for bit in (llr[:91] > 0).astype(int).tolist():
                            bits91_int = (bits91_int << 1) | bit
                        bits77_int = check_crc(bits91_int)
                        if(bits77_int):
                            msg = unpack(bits77_int)
                            if(msg not in messages):
                                messages[msg] = f"{1+len(messages):03d}:{msg}{(6.25*(fb + subfreq / NSUBFREQS), 0.16*(h0_idx + subhop / NSUBHOPS))} {nits} {subhop} {subfreq}"
                                print(messages[msg])

