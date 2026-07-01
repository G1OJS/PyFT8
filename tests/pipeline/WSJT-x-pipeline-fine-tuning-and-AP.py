#!/usr/bin/env python3

import os, sys
import numpy as np
import wave

SYM_RATE =6.25
SAMP_RATE=12000
T_CYC=15
LDPC_CONTROL = (55, 15) 

from PyFT8.receiver import unpack, check_crc

class LdpcDecoder:
    def __init__(self):
        self.CV6idx = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
        self.CV7idx = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)
        self.mC2V_prev6 = None
        self.mC2V_prev7 = None
        
    def calc_ncheck(self, llr):
        bits6 = llr[self.CV6idx] > 0
        self.parity6 = np.sum(bits6, axis=1) & 1
        bits7 = llr[self.CV7idx] > 0
        self.parity7 = np.sum(bits7, axis=1) & 1
        return int(np.sum(self.parity7) + np.sum(self.parity6))

    def _pass_messages(self, llr, CVidx, mC2V_prev, update_collector):
        if mC2V_prev is None:
            mC2V_prev = np.zeros(CVidx.shape, dtype=np.float32)
        mV2C = llr[CVidx] - mC2V_prev
        tanh_mV2C = np.tanh(-mV2C)
        tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
        try:
            tanh_mC2V = tanh_mC2V / tanh_mV2C
        except:
            tanh_mC2V = tanh_mC2V / (tanh_mV2C + 0.001)
        alpha_atanh_approx = 1.18
        mC2V_curr  = tanh_mC2V / ((tanh_mC2V - alpha_atanh_approx) * (alpha_atanh_approx + tanh_mC2V))
        np.add.at(update_collector, CVidx, mC2V_curr - mC2V_prev)
        return mC2V_curr
    
    def decode(self, llr):
        for iteration in range(LDPC_CONTROL[1]):
            update_collector = np.zeros_like(llr)
            self.mC2V_prev6 = self._pass_messages(llr, self.CV6idx, self.mC2V_prev6, update_collector)
            self.mC2V_prev7 = self._pass_messages(llr, self.CV7idx, self.mC2V_prev7, update_collector)
            llr += update_collector
            ncheck = self.calc_ncheck(llr)
            if(ncheck == 0):
                break
        return llr, ncheck, iteration 

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
                if not msg in messages:
                    messages[msg] = f"{1+len(messages):03d}: {int(0.5+origin['f0']):4d}Hz {origin['t0']-0.5:4.1f}s {' '.join(msg):25s} {ipass:03d} {nits:03d}"
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


    
