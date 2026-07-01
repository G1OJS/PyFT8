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
    baud = SAMP_RATE / 1920
    fb_0 = int(0.5 + origin['f0'] / df )
    fb_top = int(0.5 + (origin['f0'] + 8.5*baud) / df )
    fb_bot = int(0.5 + (origin['f0'] - 1.5*baud) / df )
    fft2_len = 3200
    candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
    candidate_spectrum[:(fb_top - fb_bot)] = all_audio_spectrum[fb_bot:fb_top]
    candidate_spectrum = np.roll(candidate_spectrum, (fb_0 - fb_bot))
    candidate_zsig = np.fft.ifft(candidate_spectrum)
    print(df)
    print(fb_0, fb_bot, fb_top)
    #ax.plot(np.abs(all_audio_spectrum[13000:15000]))
    #ax.plot(np.abs(candidate_spectrum))
    

    # get candidate symbol spectra x79 with df = 1 tone spacing
    candidate_tf_zgrid = np.ones((N_SYMS, 8), dtype = np.complex64)
    
    dt = (1 / SAMP_RATE) * fft1_len / fft2_len
    #ax.plot(np.linspace(0,dt*len(candidate_zsig),len(candidate_zsig)), np.abs(candidate_zsig))
    for s in range(N_SYMS):
        i0 = int(((origin['t0'])/dt) + s * 32)
        zsymb = candidate_zsig[i0:i0+32]
        if(zsymb.shape[0] == 32):
            # HARDWIRE: fft grid is off by 3 bins
            candidate_tf_zgrid[s, :] = np.fft.fft(zsymb)[3:11]

    db_grid = 20*np.log10(np.abs(candidate_tf_zgrid))
    #ax.imshow(np.clip(db_grid, np.max(db_grid)-30,None), origin = 'lower')
    
            
    return candidate_tf_zgrid        

def get_messages(wav_file):
    origins = get_initial_origins(wav_file)

# HARDWIRE: code above doesn't get f0 precisely (gets ~871)
    origins = [{'h0_idx':0, 't0':0.0, 'f0_idx':0, 'f0':873, 'score':100}]
    print(origins)

    LDPC_CONTROL = (55, 15) 
    PAYLOAD_SYMBOLS = list(range(7, 36)) + list(range(43, 72))
    wf = wave.open(wav_file, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    wf.close()
    messages = {}
    for origin in origins:
        zcand = get_candidate_tfgrid(all_audio_frames, origin)
        dBgrid = 20*np.log10(np.abs(zcand[PAYLOAD_SYMBOLS, :]))
        ax.imshow(np.clip(dBgrid, np.max(dBgrid)-30,None), origin = 'lower')
    
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
                if(msg not in messages):
                    h0_idx = origin['h0_idx']
                    messages[msg] = f"{1+len(messages):03d}:{msg:25s}{origin['f0']:7.1f}, {origin['t0']:5.1f} {llr_sd:5.1f} {nits:03d}"
                    print(messages[msg])
    return messages

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"
wav_folder = './'
nw, nt = 0, 0
fig, ax = plt.subplots()
for i in range(1,2):
    test_id = f"test_{i:02d}"
    test_id = "PyFT8_873"
    nwsjtx=1
    #with open(f"{data_folder}/{test_id}_wsjtx_2.7.0_NORM.txt", "r") as f:
    #    nwsjtx = len(f.readlines())
    messages = get_messages(f"{wav_folder}/{test_id}.wav")
    nw += nwsjtx
    nt += len(messages)
    pc = nt / nw
    print(f"{test_id} WSJTX: {nwsjtx: 03d}  This: {len(messages): 03d} Cumulative: {nw: 04d} {nt: 04d} {pc:.0%}")
    plt.show()

    
