import threading
import numpy as np
import wave
from PyFT8.time_utils import time_utils, Ticker
import os
import pyaudio
import pickle
from PyFT8.databases import call_hashes, add_call_hashes

T_CYC = 15
SYM_RATE = 6.25
SAMP_RATE = 12000
COSTAS = [3,1,4,0,6,5,2]
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))

#=========== Unpacking functions ========================================
def get_bitfields(bits, lengths):
    fields = []
    for n in lengths:
        mask = (1 << n) - 1
        fields.append(bits & mask)
        bits >>= n
    return *fields, bits

def unpack(bits):
    if not bits:
        return None
    
    i3, bits74 = get_bitfields(bits,[3])
    if i3 == 0:
        n3, bits71 = get_bitfields(bits74,[3])
        if n3 <= 4:
            return (['Free text', 'DXpedition','Field Day', 'Field Day', 'Telemetry'][n3],'not','implemented')
        else:
            return ('Unknown mode','not','implemented')
    elif i3 == 1 or i3 == 2: # 1 = Std Msg incl /R 2 = 'EU VHF' = Std Msg incl /P
        return unpack_std(bits74, i3)
    elif i3 == 3:
        return ('RTTY RU','not','implemented')
    elif i3 == 4:
        cq, rrr, swp, c58, hsh, _ = get_bitfields(bits74, [1,2,1,58,12]) 
        ca = "CQ" if cq else call_hashes.get((hsh,12), '<....>')
        cb = ""
        for i in range(12):
            cb = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"[c58 % 38] + cb
            c58 = c58 // 38
        cb =  cb.strip()
        add_call_hashes(cb)
        (ca, cb) = (cb, ca) if swp else (ca, cb)
        return (ca, cb, ('', 'RRR', 'RR73', '73')[rrr])
    elif i3 == 5:
        return ('EU VHF','not','implemented')

def unpack_std(bits74, i3):
    g16, cb29, ca29, _ = get_bitfields(bits74,[16,29,29])
    g15 = g16 & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        grid_rpt =  chr(65+a) + chr(65+b) + str(c) + str(d)
    elif g15 - 32400 <= 4:
        grid_rpt =  ('', '', 'RRR', 'RR73', '73')[g15 - 32400]
    else:
        prefix = 'R' if (g16 >> 15) else ''
        grid_rpt = prefix + f"{(g15 - 32435):+03d}"
    msg_tuple = (call_29(ca29, i3), call_29(cb29, i3), grid_rpt)
    if msg_tuple != ('','',''):
        return msg_tuple

def call_29(call_int29, i3):    
    portable_rover = call_int29 & 1
    call_int28 = call_int29>>1
    if call_int28 < 3:
        return ['DE', 'QRZ', 'CQ'][call_int28]
    elif call_int28 < 1004:
        return f"CQ {call_int28 - 3:03d}"
    elif call_int28 < 21443:
        x, txt = call_int28 - 1003, ''
        for i in range(4):
            txt = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"[int(x % 27)] + txt
            x //= 27
        return f"CQ {txt.strip()}"
    elif call_int28 < 2063592+4194303:
        return call_hashes.get((call_int28 - 2063592, 22), '<....>')
    else:
        call = standard_call28(call_int28, i3)
        if portable_rover:
            call = call + ('/P' if i3 == 2 else '/R')
        add_call_hashes(call)
        return call

def standard_call28(call_int28, i3):
    nn = call_int28 - (2063592 + 4194304)
    from string import ascii_uppercase as ltrs, digits as digs
    call_fields = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                    (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
    chars = []
    for alphabet, div in call_fields:
        idx, nn = divmod(nn, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    return call

#============== CRC ===========================================================
def check_crc(bits91_int):
    bits77_int = bits91_int >> 14
    if(bits77_int > 0):
        crc14_int = 0
        for i in range(96):
            inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
            bit14 = (crc14_int >> (14 - 1)) & 1
            crc14_int = ((crc14_int << 1) & ((1 << 14) - 1)) | inbit
            if bit14:
                crc14_int ^= 0x2757
        if(crc14_int == bits91_int & 0b11111111111111):
            return bits77_int

#============== LDPC ===========================================================
CV6idx = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
CV7idx = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)

import warnings
warnings.filterwarnings("error")

def pass_ldpc_messages(llr, CVidx, mC2V_prev, update_collector):
    mV2C = llr[CVidx] - mC2V_prev
    tanh_mV2C = np.tanh(-mV2C)
    tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
    orig_err = np.geterr()
    np.seterr(all = 'ignore')
    tanh_mC2V = np.divide(tanh_mC2V, tanh_mV2C)
    np.seterr(**orig_err)
    alpha_atanh_approx = 1.18
    mC2V_curr  = tanh_mC2V / ((tanh_mC2V - alpha_atanh_approx) * (alpha_atanh_approx + tanh_mC2V))
    np.add.at(update_collector, CVidx, mC2V_curr - mC2V_prev)
    return mC2V_curr

def ldpc_decode(llr, max_ncheck0, max_iters):
    mC2V_prev6, mC2V_prev7 = np.zeros(CV6idx.shape, dtype=np.float32), np.zeros(CV7idx.shape, dtype=np.float32)
    for n_its in range(max_iters):
        bits6, bits7 = llr[CV6idx] > 0, llr[CV7idx] > 0
        parity6, parity7 = np.sum(bits6, axis=1) & 1, np.sum(bits7, axis=1) & 1
        ncheck = int(np.sum(parity7) + np.sum(parity6))
        if n_its == 0 and ncheck > max_ncheck0:
            return None
        if ncheck == 0:
            bits91_int = 0
            for bit in (llr[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            msg_tuple = unpack(bits77_int)
            if msg_tuple:
                return (msg_tuple, n_its)
        else:
            update_collector = np.zeros_like(llr)
            mC2V_prev6 = pass_ldpc_messages(llr, CV6idx, mC2V_prev6, update_collector)
            mC2V_prev7 = pass_ldpc_messages(llr, CV7idx, mC2V_prev7, update_collector)
            llr += update_collector

#============== AUDIO IN ===========================================================
class AudioIn:
    def __init__(self, search_freq_range, wav_files = None):
        self.search_hps, self.search_bpt = 4, 2
        self.search_freq_range = search_freq_range
        self.wav_files = wav_files
        self.search_fft_len = int(self.search_bpt * SAMP_RATE // SYM_RATE)
        self.df = SYM_RATE / self.search_bpt
        self.search_f0_idx_range = [int(self.search_freq_range[0] / self.df),
                                    int((self.search_freq_range[1]) / self.df)]
        self.search_fft_window = np.hanning(self.search_fft_len).astype(np.float32)
        self.search_hops_per_cycle = int(T_CYC * SYM_RATE * self.search_hps)
        self.search_hops_per_grid = 2*self.search_hops_per_cycle
        self.dt = T_CYC / self.search_hops_per_cycle
        self.search_grid = np.ones((self.search_hops_per_grid, self.search_f0_idx_range[1]  + 8 * self.search_bpt ), dtype = np.float32)
        self.waterfall_data = self.search_grid
        self.search_grid_ptr = 0
        self.search_audio_buffer = np.zeros(self.search_fft_len, dtype=np.float32)
        self.search_fft_in = np.zeros(self.search_fft_len, dtype=np.float32)
        self.cycle_audio_buffer = np.zeros(192000, dtype=np.float32)
        self.cycle_audio_buffer_ptr = 0
        
    def start_wav_load(self):
        threading.Thread(target = self.load_wavs, args =(self.wav_files,)).start()
        self.search_grid_ptr = 0
        self.cycle_audio_buffer_ptr = 0

    def load_wavs(self, wav_paths):
        hop_dt = 1 / (SYM_RATE * self.search_hps) 
        samples_perhop = int(SAMP_RATE / (SYM_RATE * self.search_hps))
        adj = 1
        self.sync_pointer_to_wall_clock()
        for wav_path in wav_paths:
            wf = wave.open(wav_path, "rb")
            hoptimes = []
            th = time_utils.time()
            frames = wf.readframes(samples_perhop)
            while frames:
                delay = hop_dt*adj - (time_utils.time()-th)
                if(delay>0): time_utils.sleep(delay)
                th = time_utils.time()
                hoptimes.append(th)
                self._callback(frames, None, None, None)
                frames = wf.readframes(samples_perhop)
            wf.close()
            deltas = np.diff(hoptimes)
            meanhop, sdhop = 1000*np.mean(deltas), 1000*np.std(deltas)
            adj = adj * 40/meanhop
            print(f"[Receiver] read wav file with hop mean = {meanhop:6.2f}ms, sd =  {sdhop:6.2f}ms")
        for run_on in range(1 * self.search_hops_per_cycle):
            time_utils.sleep(hop_dt)
            self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid
            
    def start_streamed_audio(self, input_device_idx):
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = SAMP_RATE, input = True, input_device_index = input_device_idx,
            frames_per_buffer = int(SAMP_RATE / (SYM_RATE * self.search_hps)), stream_callback=self._callback,)
        self.sync_pointer_to_wall_clock()
        self.stream.start_stream()

    def sync_pointer_to_wall_clock(self, tolerance = 0.01):
        t = time_utils.time()
        search_grid_ptr = int(t * SYM_RATE * self.search_hps) % self.search_hops_per_grid
        cycle_audio_buffer_ptr = int(t * SAMP_RATE) % (SAMP_RATE * T_CYC)
        delta1 = np.abs(cycle_audio_buffer_ptr - self.cycle_audio_buffer_ptr) / SAMP_RATE 
        delta2 = np.abs(cycle_audio_buffer_ptr - self.cycle_audio_buffer_ptr + SAMP_RATE * T_CYC) / SAMP_RATE 
        delta = np.min([delta1, delta2])
        if np.abs(delta) > tolerance:
            print(f"Sync grid pointers (delta = {delta*1000:6.1f}ms)")
            self.search_grid_ptr, self.cycle_audio_buffer_ptr = search_grid_ptr, cycle_audio_buffer_ptr
       
    def find_device(self, device_str_contains):
        pya = pyaudio.PyAudio()
        for dev_idx in range(pya.get_device_count()):
            name = pya.get_device_info_by_index(dev_idx)['name']
            match = True
            for pattern in device_str_contains:
                if (not pattern in name): match = False
            if(match):
                return dev_idx
        print(f"[Audio] No input audio device found matching {device_str_contains}")

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.search_audio_buffer[:-ns] = self.search_audio_buffer[ns:]
        self.search_audio_buffer[-ns:] = samples
        np.multiply(self.search_audio_buffer, self.search_fft_window, out = self.search_fft_in)
        z = np.fft.rfft(self.search_fft_in)[:self.search_grid.shape[1]]
        self.search_grid[self.search_grid_ptr, :] = 20*np.log10(np.abs(z))
        self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid

        self.cycle_audio_buffer[self.cycle_audio_buffer_ptr:self.cycle_audio_buffer_ptr + ns] = samples
        self.cycle_audio_buffer_ptr = (self.cycle_audio_buffer_ptr + ns) % (SAMP_RATE * T_CYC)
        return (None, pyaudio.paContinue)


#============== CANDIDATE ===========================================================

ap_patterns = [
                [0, []],                                                                # no AP
                [0, [0,0,0,0,0 ,0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,1,0,0]],  # CQ
                [58,[0,1, 1,1,1,1,1, 0,0,1,1,1, 0,1,0,1,0, 0,1]],                       # RR73
                [58,[0,1, 1,1,1,1,1, 0,1,0,0,1, 0,1,0,0,0, 0,1]],                       # 73
                [58,[0,1, 1,1,1,1,1, 0,1,0,0,1, 0,0,1,0,0, 0,1]],                       # RRR
              ]

class Candidate:
    def __init__(self, cyclestart, origin, llr_sd_min = 5):
        self.cyclestart, self.origin = cyclestart, origin
        self.demap_started, self.decode_completed = 0, 0
        self.msg_tuple = None
        self.llr_sd_min = llr_sd_min
        self.llr_sd, self.ipass, self.n_its, self.snr = 0, 0, 0, -30
        csync = np.full((7, 7), -1/6, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            csync[sym_idx, tone] = 1.0
        self.csync_7x7 =  csync.ravel()

    def get_tfgrid(self, all_audio_spectrum, fb_0, fb_bot, fb_top, tb_0): 
        N_SYMS = 79
        fft2_len = 3200
        candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
        candidate_spectrum[:(fb_top - fb_bot)] = all_audio_spectrum[fb_bot:fb_top]
        candidate_spectrum = np.roll(candidate_spectrum, -(fb_0 - fb_bot))
        candidate_zsig = np.fft.ifft(candidate_spectrum)
        # get candidate symbol spectra x79 with df = 1 tone spacing
        cgrid = np.ones((N_SYMS, 8), dtype = np.float32)
        
        for s in range(N_SYMS):
            i0 = tb_0 + s * 32
            zsymb = candidate_zsig[i0:i0+32]
            if(zsymb.shape[0] == 32):
                cgrid[s, :] = np.abs(np.fft.fft(zsymb))[:8]

        score = float(np.dot(cgrid[36:43, :7].ravel(), self.csync_7x7))
        return cgrid, score

    def demap(self, all_audio_spectrum):
        df = SAMP_RATE / 192000
        f0, t0 = self.origin['f0'], self.origin['t0']
        fb_0 = int(0.5 + f0 / df )
        fb_top = int(0.5 + (f0 + 8.5*SYM_RATE) / df )
        fb_bot = int(0.5 + (f0 - 1.5*SYM_RATE) / df )
        dt = 0.005
        tb_0 = int(t0/dt)
        ftweak, ttweak = 0, 0

        ttweaks = range(-15, 5, 4) # 4 steps = 20ms = 1/8 sample
        scores = []
        for ttweak in ttweaks:
            cgrid, score = self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(score)
        ttweak = ttweaks[np.argmax(scores)]

        ftweaks = range(-32, 45, 16) # 16 steps = 1Hz, 6.25Hz = 100 steps
        scores = []
        for ftweak in ftweaks:
            cgrid, score = self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(score)
        ftweak = ftweaks[np.argmax(scores)]

        self.ftweak, self.ttweak = ftweak, ttweak
        cgrid, score = self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
        
        p = 20*np.log10(cgrid[PAYLOAD_SYMB_IDXS, :])
        self.snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        self.llr_sd = np.std(llr)
        self.llr = 2.83 * llr / self.llr_sd
          
    def decode(self):
        if self.llr_sd > self.llr_sd_min:
            for max_its in [15]:
                for ipass, (b0, ap_pattern) in enumerate(ap_patterns):
                    llr = self.llr.copy()
                    for b, bval in enumerate(ap_pattern):
                        llr[b0 + b] = (bval*2-1) * 5
                    if ipass == 1:
                        llr[74:76] = -5
                        llr[76] = 5
                    success = ldpc_decode(llr, 50, max_its)
                    if success:
                        self.msg_tuple, self.n_its = success
                        self.ipass = ipass
                        break
        self.decode_completed = time_utils.time()
        
#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, search_freq_range, input_device_keywords, wav_files, on_decode, on_busy_profile = None, verbose = False):
        self.audio_in = AudioIn(search_freq_range, wav_files)
        self.wav_files = wav_files
        if input_device_keywords is not None:
            self.input_device_idx = self.audio_in.find_device(input_device_keywords)
            if not self.input_device_idx:
                print("[Receiver] No input device")
                sys.exit(1)
            self.audio_in.start_streamed_audio(self.input_device_idx)
        self.on_decode = on_decode
        self.on_busy_profile = on_busy_profile
        self.verbose = verbose
        search_timerange = [-2, 4]
        self.search_h0_range = [int((t+0.5)*self.audio_in.search_hps*SYM_RATE) for t in search_timerange]
        self.search_start_hop = self.search_h0_range[1] + 43 * self.audio_in.search_hps
        dt = 1.0 / (SYM_RATE * self.audio_in.search_hps)
        time_utils.set_cycle_length(T_CYC)
        if wav_files is not None:
            time_utils.set_time_offset()
            self.audio_in.start_wav_load()
        print(f"Search hops {self.search_h0_range[0]:3d} to {self.search_h0_range[1]:3d}")
        print(f"Start search at hop {self.search_start_hop:3d}")
        time_utils.sleep(0.5)
        threading.Thread(target=self.manage_cycle, daemon=True).start()
        
    def search(self, cyclestart, odd_even, sync_score_min = 90):
        cands = []
        cycle_h0 = int(odd_even * T_CYC * SYM_RATE * self.audio_in.search_hps)
        base_search_hops = 36 * self.audio_in.search_hps + np.arange(7) * self.audio_in.search_hps + self.audio_in.search_hps
        csync = np.full((7, 7 * self.audio_in.search_bpt), -1/6, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            fbins = range(tone * self.audio_in.search_bpt, (tone+1) * self.audio_in.search_bpt)
            csync[sym_idx, fbins] = 1.0
        csync_search = csync.ravel()
        for f0_idx in range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1], 2):
            p = self.audio_in.search_grid[:, f0_idx: f0_idx + 7*self.audio_in.search_bpt]
            origin = {'score':0}
            for h0_idx in range(self.search_h0_range[0], self.search_h0_range[1]):
                score = float(np.dot(p[h0_idx + cycle_h0 + base_search_hops, :].ravel(), csync_search))
                test_sync = {'cycle':odd_even, 'h0_idx':h0_idx, 
                             't0':h0_idx/(self.audio_in.search_hps * SYM_RATE),
                             'f0':SYM_RATE * f0_idx / self.audio_in.search_bpt, 'score':score}
                if test_sync['score'] > origin['score']:
                    origin = test_sync
            if origin['score'] > sync_score_min:
                c = Candidate(cyclestart, origin)
                cands.append(c)
        return cands

    def get_busy_profile(self):
        from numpy.lib.stride_tricks import sliding_window_view
        h0 = 0 if self.odd_even == 0 else self.audio_in.search_hops_per_cycle+1    
        fbin_sum = np.sum(self.audio_in.search_grid[h0:self.audio_in.search_grid_ptr, :], axis = 0)
        windows = sliding_window_view(fbin_sum, 8*self.audio_in.search_bpt)
        bp = windows.max(axis=1) 
        return bp, self.audio_in.df, self.odd_even
        
    def manage_cycle(self):
        dashes = "======================================================"
        candidates = []
        duplicate_filter = set()
        search_grid_ptr_prev = 0
        print("Rx running")
        ticker_cycle_rollover = Ticker(0)
        ticker_search_for_syncs = Ticker(self.search_start_hop,
                                         timing_function = lambda: self.audio_in.search_grid_ptr,
                                         cycle_length = self.audio_in.search_hops_per_cycle)
        hopspersym = SYM_RATE * self.audio_in.search_hps
        last_spectrum_calc = -1
        
        while True:
            time_utils.sleep(0.040)
            if self.wav_files is None and ticker_cycle_rollover.ticked():                
                self.audio_in.sync_pointer_to_wall_clock(0.5)
            odd_even = int((self.audio_in.search_grid_ptr) / self.audio_in.search_hops_per_cycle)
            
            to_decode = []
            for c in candidates:
                if not c.demap_started:
                    odd_even_offset = c.origin['cycle'] * self.audio_in.search_hops_per_cycle
                    cand_abs_h0_idx = (c.origin['h0_idx'] + PAYLOAD_SYMB_IDXS[0] - 1) * hopspersym + odd_even_offset
                    cand_abs_hf_idx = (c.origin['h0_idx'] + PAYLOAD_SYMB_IDXS[1] + 1) * hopspersym + odd_even_offset
                    if not (cand_abs_h0_idx <= self.audio_in.search_grid_ptr <= cand_abs_hf_idx):
                        if self.audio_in.search_grid_ptr != last_spectrum_calc: # only calc full spectrum if more samples received
                            all_audio_spectrum = np.fft.rfft(self.audio_in.cycle_audio_buffer)
                        last_spectrum_calc = self.audio_in.search_grid_ptr
                        c.demap(all_audio_spectrum)
                        h2s = 1/(SYM_RATE * self.audio_in.search_hps)
                        c.demap_started = self.audio_in.search_grid_ptr*h2s
                       #print(f"Demap {len(candidates)} {cand_abs_h0_idx*h2s:5.1f} - {cand_abs_hf_idx*h2s:5.1f} {c.llr_sd}")
                if not c.decode_completed:
                    to_decode.append(c)

            to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
            for c in to_decode[:15]:
                c.decode()
                if c.msg_tuple:
                    key = c.cyclestart['string'] + ''.join(c.msg_tuple)
                    if (key not in duplicate_filter):
                        duplicate_filter.add(key)
                        self.on_decode(c)

            if ticker_search_for_syncs.ticked():
                hstart = self.audio_in.search_grid_ptr
                tstart = hstart / (SYM_RATE * self.audio_in.search_hps)
                time_utils.tlog(f"[Cycle manager] start search at hop {hstart} ({tstart:6.2f}s)", verbose = True)
                cyclestart = time_utils.cyclestart(time_utils.time())
                timeouts = len([c for c in candidates if not c.decode_completed])
                if timeouts:
                    print(f"Warning - {timeouts} candidates ran out of decoding time")
                candidates = self.search(cyclestart, odd_even)
                hstop = self.audio_in.search_grid_ptr
                if not self.on_busy_profile is None:
                   self.on_busy_profile(*self.get_busy_profile())
                tsearch = (hstop-hstart)/ (SYM_RATE * self.audio_in.search_hps)
                time_utils.tlog(f"[Cycle manager] New spectrum searched in {tsearch}s -> {len(candidates)} candidates", verbose = True) 

