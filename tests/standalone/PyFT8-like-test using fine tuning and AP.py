#!/usr/bin/env python3

import os, sys
import numpy as np
import wave

SYM_RATE =6.25
SAMP_RATE=12000
T_CYC=15
zgrid_main = None

from PyFT8.receiver import unpack, LdpcDecoder, check_crc
  
def get_initial_origins(wav_file ):
    global zgrid_main, HPS, BPT
    HPS=4
    BPT=2
    H0_RANGE = [int(-2*HPS/0.16), int(5*HPS/0.16)]
    COSTAS = [3,1,4,0,6,5,2]
    BASE_COSTAS_HOPS =  np.arange(7) * HPS
    fft_len = int( BPT * SAMP_RATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    max_freq = 2900
    nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
    audio_buffer = np.zeros(fft_len, dtype=np.float32)
    fft_in = np.zeros(fft_len, dtype=np.float32)
    fft_window = fft_window=np.hanning(fft_len).astype(np.float32)
    hops_per_grid = T_CYC * SYM_RATE * HPS
    if (int(hops_per_grid) != hops_per_grid):
        print("Warning - non-integer number of hops per grid")
    hops_per_grid = int(hops_per_grid)
    zgrid_main = np.ones((hops_per_grid, nFreqs), dtype = np.complex64) 
    samples_perhop = int(SAMP_RATE / (SYM_RATE * HPS))
    zgrid_main_ptr = 0

    wf = wave.open(wav_file, "rb")
    frames = wf.readframes(samples_perhop)
    while frames:
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        audio_buffer[:-ns] = audio_buffer[ns:]
        audio_buffer[-ns:] = samples
        np.multiply(audio_buffer, fft_window, out=fft_in)
        zgrid_main[zgrid_main_ptr, :] = np.fft.rfft(fft_in)[:nFreqs]
        zgrid_main_ptr = (zgrid_main_ptr+1) % hops_per_grid
        frames = wf.readframes(samples_perhop)
    wf.close()

    dt = 1.0 / (SYM_RATE * HPS)
    csync = np.full((7, 7 * BPT), -1/6, np.float32)
    for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
        fbins = range(tone * BPT, (tone+1) * BPT)
        csync[sym_idx, fbins] = 1.0
    csync_flat =  csync.ravel()

    origins = []
    f_min, f_max = 100, 2900
    for fb in range(int(f_min*BPT/SYM_RATE), nFreqs - 8 * BPT):
        zstrip = zgrid_main[:, fb: fb+8*BPT]
        dBgrid = 20*np.log10(np.abs(zstrip) + 1e-12)

        origin = {'score':0}
        for h0_idx in range(H0_RANGE[0], H0_RANGE[1]):
            sync_score = float(np.dot(dBgrid[h0_idx + BASE_COSTAS_HOPS + 36 * HPS, :7*BPT].ravel(), csync_flat))
            test_sync = {'t0':h0_idx/(HPS * SYM_RATE), 'f0':SYM_RATE * fb / BPT, 'score':sync_score}
            if test_sync['score'] > origin['score']:
                origin = test_sync
        if origin['score'] > 20:
            origins.append(origin)

    return origins

def get_message(wav_file, origin):
    LDPC_CONTROL = (50, 15) 
    PAYLOAD_SYMBOLS = list(range(7, 36)) + list(range(43, 72))

    c = BPT//2
    A1 = [a * BPT +c for a in [4,5,6,7]]
    A0 = [a * BPT +c for a in [0,1,2,3]]
    B1 = [a * BPT +c for a in [2,3,4,7]]
    B0 = [a * BPT +c for a in [0,1,5,6]]
    C1 = [a * BPT +c for a in [1,2,6,7]]
    C0 = [a * BPT +c for a in [0,3,4,5]]
    target_params = [3.5, 3.7]
    h0_idx = int(origin['t0'] * HPS * SYM_RATE)
    f0_idx = int(origin['f0'] * BPT / SYM_RATE)
    gridsize = zgrid_main.shape[0]
    zcand = zgrid_main[[(h0_idx + HPS*s) % gridsize for s in PAYLOAD_SYMBOLS],:]
    zcand = zcand[:, f0_idx + np.array(range(8*BPT))]
    dBgrid = 20*np.log10(np.abs(zcand))
    pmax = np.max(dBgrid)
    snr = np.clip(int(pmax - np.min(dBgrid) - 58), -24, 24)
    p = np.clip(dBgrid - pmax, -80, 0)
    llra = np.max(p[:, A1], axis=1) - np.max(p[:, A0], axis=1)
    llrb = np.max(p[:, B1], axis=1) - np.max(p[:, B0], axis=1)
    llrc = np.max(p[:, C1], axis=1) - np.max(p[:, C0], axis=1)
    llr = np.column_stack((llra, llrb, llrc))
    llr = llr.ravel() / 10
    llr_sd = np.std(llr)
    llr = target_params[0] * llr / (1e-12 + llr_sd)
    llr0 = np.clip(llr, -target_params[1], target_params[1])
    apmag = np.max(np.abs(llr0))*1.01

    ap_patterns = [
                    [0, []],                                                            # no AP
                    [0, [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0]],   # CQ
                    [58,[0,1,1,1,1,1,1,0,0,1,1,1,0,1,0,1,0,0,1]],                       # RR73
                    [58,[0,1,1,1,1,1,1,0,1,0,0,1,0,1,0,0,0,0,1]],                       # 73
                    [58,[0,1,1,1,1,1,1,0,1,0,0,1,0,0,1,0,0,0,1]],                       # RRR
                  ]
    msg, ipass = None, 0
    while (not msg) and ipass < len(ap_patterns):
        llr = llr0
        b0, ap_pattern = ap_patterns[ipass]
        for b, bval in enumerate(ap_pattern):
            llr[b0 + b] = (bval*2-1) * apmag
        ipass += 1
        ldpc = LdpcDecoder()
        nits = 0
        ncheck = ldpc.calc_ncheck(llr)
        if 0 < ncheck <= LDPC_CONTROL[0]:
            llr, ncheck, nits = ldpc.decode(llr)
        bits91_int = 0
        for bit in (llr[:91] > 0).astype(int).tolist():
            bits91_int = (bits91_int << 1) | bit
        bits77_int = check_crc(bits91_int)
        if(bits77_int):
            msg = unpack(bits77_int)
            if msg:
                return ' '.join(msg)


def process_file(wav_file):
    origins = get_initial_origins(wav_file)
    messages = {}
    for origin in origins:
        msg = get_message(wav_file, origin)
        if(msg and msg not in messages):
            messages[msg] = f"{1+len(messages):03d}:{msg:25s}"
            print(messages[msg])        
    return messages

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"

nw, nt = 0, 0
for i in range(1,39):
    test_id = f"test_{i:02d}"
    with open(f"{data_folder}/{test_id}_wsjtx_2.7.0_NORM.txt", "r") as f:
        nwsjtx = len(f.readlines())
    messages = process_file(f"{wav_folder}/{test_id}.wav")
    nw += nwsjtx
    nt += len(messages)
    pc = nt / nw
    print(f"{test_id} WSJTX: {nwsjtx: 03d}  This: {len(messages): 03d} Cumulative: {nw: 04d} {nt: 04d} {pc:.0%}")


    
