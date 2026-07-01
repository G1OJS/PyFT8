#!/usr/bin/env python3

import os, sys
import numpy as np
import wave
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
sys.path.insert(0, repo_root)

SYM_RATE = 6.25
SAMP_RATE=12000
T_CYC=15

from PyFT8.receiver import unpack, LdpcDecoder, check_crc

def get_initial_origins(wav_file ):
    global zgrid_main, HPS, BPT
    HPS=4
    BPT=2
    COSTAS = [3,1,4,0,6,5,2]
    HOPDELAY = HPS
    BASE_COSTAS_HOPS =  np.arange(7) * HPS + HOPDELAY
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
        for h0_idx in range(0, int(5*HPS/0.16)):
            sync_score = float(np.dot(dBgrid[h0_idx + BASE_COSTAS_HOPS, :7*BPT].ravel(), csync_flat))
            test_sync = {'t0':h0_idx/(HPS * SYM_RATE), 'f0':SYM_RATE * fb / BPT, 'score':sync_score}
            if test_sync['score'] > origin['score']:
                origin = test_sync
        if origin['score'] > 200:
            origins.append(origin)

    return origins

def get_candidate_tfgrid(all_audio_frames, origin):
    N_SYMS = 79
    
    # get full audio spectrum (later - move outside and do once on wav load)
    fft1_len = 192000
    samples = np.zeros(fft1_len)
    samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
    samples[:len(samps_in)] = samps_in 
    all_audio_spectrum = np.fft.fft(samples)

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
    origins = get_initial_origins(wav_file)

    LDPC_CONTROL = (55, 15) 
    PAYLOAD_SYMBOLS = list(range(7, 36)) + list(range(43, 72))
    wf = wave.open(wav_file, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    wf.close()
    messages = {}

    csync = np.full((7, 7), -1/6, np.float32)
    for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
        csync[sym_idx, tone] = 1.0
    csync_flat =  csync.ravel()
    for origin in origins:
        print("\nNew coarse origin")

        zcand = get_candidate_tfgrid(all_audio_frames, origin)
        score = float(np.dot(np.abs(zcand[:7, :7]).ravel(), csync_flat))
        origin = {'t0':origin['t0'], 'f0':origin['f0'], 'score':float(score)}
        print(origin)
                      
        ttweaks = np.arange(-50, 51, 10)/1000
        scores = []
        for ttweak in ttweaks:
            tmp_origin = {'t0':origin['t0']+ttweak, 'f0':origin['f0'], 'score':0}
            zcand = get_candidate_tfgrid(all_audio_frames, tmp_origin)
            score = float(np.dot(np.abs(zcand[:7, :7]).ravel(), csync_flat))
            scores.append(score)
            #ax.imshow(np.abs(zcand), origin = 'lower')
            #plt.pause(0.5)
            #print(ttweak, score)
        ttweak = float(ttweaks[np.argmax(scores)])
        origin = {'t0':origin['t0']+ttweak, 'f0':origin['f0'], 'score':np.max(scores)}
        print(origin)
        
        ftweaks = np.arange(-2.5, 2.6, 0.5)
        scores = []
        for ftweak in ftweaks:
            tmp_origin = {'t0':origin['t0'], 'f0':origin['f0']+ftweak, 'score':0}
            zcand = get_candidate_tfgrid(all_audio_frames, tmp_origin)
            score = float(np.dot(np.abs(zcand[:7, :7]).ravel(), csync_flat))
            scores.append(score)
            #ax.imshow(np.abs(zcand), origin = 'lower')
            #plt.pause(0.5)
            #print(ftweak, score)
        ftweak = float(ftweaks[np.argmax(scores)])
        origin = {'t0':origin['t0'], 'f0':origin['f0']+ftweak, 'score':np.max(scores)}
        print(origin)

        zcand = get_candidate_tfgrid(all_audio_frames, origin)
        dBgrid = 20*np.log10(np.abs(zcand[PAYLOAD_SYMBOLS, :]))        
        ax.imshow(np.clip(dBgrid, np.max(dBgrid)-30,None), origin = 'lower')
        plt.pause(0.5)
        pmax = np.max(dBgrid)
        snr = np.clip(int(pmax - np.min(dBgrid) - 58), -24, 24)
        p = np.clip(dBgrid - pmax, -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        llr_sd = np.std(llr)
        llr = 3.5 * llr / (1e-12 + llr_sd)
        llr = np.clip(llr, -3.7, 3.7)
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
                msg = ' '.join(msg)
                print(msg)

fig, ax = plt.subplots()
get_messages(f"PyFT8_873.wav")


    
