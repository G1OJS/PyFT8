#!/usr/bin/env python3

import os, sys
import numpy as np
import wave

SYM_RATE =6.25
SAMP_RATE=12000
T_CYC=15
LDPC_CONTROL = (55, 15) 

from PyFT8.receiver import unpack, check_crc, ldpc_decode

def get_initial_origins(wav_file ):

    HPS=4
    BPT=2
    COSTAS = [3,1,4,0,6,5,2]
    HOPDELAY = HPS
    BASE_COSTAS_HOPS =  np.arange(7) * HPS + HOPDELAY
    F_MIN, F_MAX = 100, 2900

    fft_len = int( BPT * SAMP_RATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    nFreqs = int(fft_out_len * 2 * F_MAX / SAMP_RATE)
    audio_buffer = np.zeros(fft_len, dtype=np.float32)
    fft_in = np.zeros(fft_len, dtype=np.float32)
    fft_window = np.hanning(fft_len).astype(np.float32)
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
    for fb in range(int(F_MIN*BPT/SYM_RATE), nFreqs - 8 * BPT):
        zstrip = zgrid_main[:, fb: fb+8*BPT]
        p = 20*np.log10(np.abs(zstrip) + 1e-12)
        #p = np.abs(zstrip)

        origin = {'score':0}
        for h0_idx in range(int(-2*HPS/0.16), int(5*HPS/0.16)):
            sync_score = float(np.dot(p[h0_idx + 36*HPS + BASE_COSTAS_HOPS, :7*BPT].ravel(), csync_flat))
            test_sync = {'t0':h0_idx/(HPS * SYM_RATE), 'f0':SYM_RATE * fb / BPT, 'score':sync_score}
            if test_sync['score'] > origin['score']:
                origin = test_sync
        if origin['score'] > 100:
            origins.append(origin)

    return origins

def get_candidate_tfgrid(all_audio_spectrum, origin):
    fft1_len = len(all_audio_spectrum)
    N_SYMS = 79
    
    # downsample to 32 samples per symbol / 200 samples per sec
    df = SAMP_RATE / fft1_len
    fb_0 = int(0.5 + origin['f0'] / df )
    fb_top = int(0.5 + (origin['f0'] + 8.5*SYM_RATE) / df )
    fb_bot = int(0.5 + (origin['f0'] - 1.5*SYM_RATE) / df )
    fft2_len = 3200
    candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
    candidate_spectrum[:(fb_top - fb_bot)] = all_audio_spectrum[fb_bot:fb_top]
    candidate_spectrum = np.roll(candidate_spectrum, -(fb_0 - fb_bot))
    candidate_zsig = np.fft.ifft(candidate_spectrum)

    # get candidate symbol spectra x79 with df = 1 tone spacing
    candidate_tf_zgrid = np.ones((N_SYMS, 8), dtype = np.complex64)
    dt = (1 / SAMP_RATE) * fft1_len / fft2_len
    for s in range(N_SYMS):
        i0 = int(((origin['t0'])/dt) + s * 32)
        zsymb = candidate_zsig[i0:i0+32]
        if(zsymb.shape[0] == 32):
            candidate_tf_zgrid[s, :] = np.fft.fft(zsymb)[:8]
    
    return candidate_tf_zgrid        

def get_messages(wav_file):
    # get full audio spectrum 
    wf = wave.open(wav_file, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    wf.close()
    fft1_len = 192000
    samples = np.zeros(fft1_len)
    samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
    samples[:len(samps_in)] = samps_in 
    all_audio_spectrum = np.fft.fft(samples)

    origins = get_initial_origins(wav_file)
    PAYLOAD_SYMBOLS = list(range(7, 36)) + list(range(43, 72))    
    messages = {}

    csync = np.full((7, 7), -1/6, np.float32)
    for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
        csync[sym_idx, tone] = 1.0
    csync_flat =  csync.ravel()
    print(f"{len(origins)} candidates")
    for origin in origins:
        
        ttweaks = np.arange(-50, 51, 10)/1000
        scores = []
        for ttweak in ttweaks:
            tmp_origin = {'t0':origin['t0']+ttweak, 'f0':origin['f0'], 'score':0}
            zcand = get_candidate_tfgrid(all_audio_spectrum, tmp_origin)
            score = float(np.dot(np.abs(zcand[36:43, :7]).ravel(), csync_flat))
            scores.append(score)
        ttweak = float(ttweaks[np.argmax(scores)])
        origin = {'t0':origin['t0']+ttweak, 'f0':origin['f0'], 'score':np.max(scores)}
        
        ftweaks = np.arange(-2.5, 2.6, 0.5)
        scores = []
        for ftweak in ftweaks:
            tmp_origin = {'t0':origin['t0'], 'f0':origin['f0']+ftweak, 'score':0}
            zcand = get_candidate_tfgrid(all_audio_spectrum, tmp_origin)
            score = float(np.dot(np.abs(zcand[36:43, :7]).ravel(), csync_flat))
            scores.append(score)
        ftweak = float(ftweaks[np.argmax(scores)])
        origin = {'t0':origin['t0'], 'f0':origin['f0']+ftweak, 'score':np.max(scores)}

        zcand = get_candidate_tfgrid(all_audio_spectrum, origin)
        p = 20*np.log10(np.abs(zcand[PAYLOAD_SYMBOLS, :]))
        snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        llr_sd = np.std(llr)
        llr = 3.5 * llr / (1e-12 + llr_sd)        
        llr0 = np.clip(llr, -3.7, 3.7)
        apmag = np.max(np.abs(llr0))*1.01

        ap_patterns = [
                        [0, []],                                                            # no AP
                        [0, [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0]],   # CQ
                        [58,[0,1,1,1,1,1,1,0,0,1,1,1,0,1,0,1,0,0,1]],                       # RR73
                        [58,[0,1,1,1,1,1,1,0,1,0,0,1,0,1,0,0,0,0,1]],                       # 73
                        [58,[0,1,1,1,1,1,1,0,1,0,0,1,0,0,1,0,0,0,1]],                       # RRR
                      ]
        msg, ipass = None, 0
        max_ncheck = LDPC_CONTROL[0]
        while (not msg) and ipass < len(ap_patterns):
            llr = llr0.copy()
            b0, ap_pattern = ap_patterns[ipass]
            for b, bval in enumerate(ap_pattern):
                llr[b0 + b] = (bval*2-1) * apmag
            ipass += 1
            msg_tuple, max_ncheck, n_its = ldpc_decode(llr, max_ncheck)
            if msg_tuple:
                msg = ' '.join(msg_tuple)
                if not msg in messages:
                    messages[msg] = f"{1+len(messages):03d}: {int(0.5+origin['f0']):4d}Hz {origin['t0']-0.5:4.1f}s {msg:25s} {ipass:03d} {n_its:03d}"
                    print(messages[msg])
    return messages


data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"

nw, nt = 0, 0
for i in range(1,39):
    test_id = f"test_{i:02d}"
    with open(f"{data_folder}/{test_id}_wsjtx_2.7.0_NORM.txt", "r") as f:
        nwsjtx = len(f.readlines())
    messages = get_messages(f"{wav_folder}/{test_id}.wav")
    nw += nwsjtx
    nt += len(messages)
    pc = nt / nw
    print(f"{test_id} WSJTX: {nwsjtx: 03d}  This: {len(messages): 03d} Cumulative: {nw: 04d} {nt: 04d} {pc:.0%}")


    
