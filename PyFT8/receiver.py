import threading
import numpy as np
import wave
import time
from PyFT8.time_utils import global_time_utils, Ticker
import os
import pyaudio
import pickle

T_CYC = 15
HPS = 4
BPT =2
SYM_RATE = 6.25
SAMP_RATE = 12000

t2h = HPS/0.16
LLR_SD_MIN = 0.5
LDPC_CONTROL = (45, 12) 
H0_RANGE = [int(0 *t2h), int(4 *t2h)]
H_SEARCH_0 = H0_RANGE[1] + 7 * HPS
H_SEARCH_1 = H0_RANGE[1] + 43 * HPS

BASE_FREQ_IDXS = np.array([BPT // 2 + BPT * t for t in range(8)])
symbol_idxs = list(range(7, 36)) + list(range(43, 72))
BASE_PAYLOAD_HOPS = np.array([HPS * s for s in symbol_idxs])
LAST_BASE_PAYLOAD_HOP = BASE_PAYLOAD_HOPS[-1]
COSTAS = [3,1,4,0,6,5,2]
BASE_COSTAS_HOPS =  np.arange(7) * HPS
HOPS_PER_CYCLE = int(T_CYC * SYM_RATE * HPS)
HOPS_PER_GRID = 2 * HOPS_PER_CYCLE

global_time_utils.set_cycle_length(T_CYC)

global hashes
hashes = {}
#=========== Unpacking functions ========================================
def get_bits(bits, n):
    mask = (1 << n) - 1
    out = bits & mask
    bits >>= n
    return out, bits

def unpack(bits):
    i3, bits = get_bits(bits,3)
    if i3 == 0:
        n3, bits = get_bits(bits,3)
        if n3 == 0:
            return ('Free text','not','implemented')
        else:
            return (['DXpedition','Field Day', 'Field Day', 'Telemetry'][n3-1],'not','implemented')
    elif i3 == 1 or i3 == 2: # 1 = Std Msg incl /R 2 = 'EU VHF' = Std Msg incl /P
        gr, bits = get_bits(bits,16)
        cb, bits = get_bits(bits,29)
        ca, bits = get_bits(bits,29)
        return (call_28(ca, i3), call_28(cb, i3), decode_grid(gr))
    elif i3 == 3:
        return ('RTTY RU','not','implemented')
    elif i3 == 4:
        cq_, bits = get_bits(bits,1)
        rrr, bits = get_bits(bits,2)
        swp, bits = get_bits(bits,1)
        c58, bits = get_bits(bits,58)
        hsh, bits = get_bits(bits,12)
        ca = "CQ" if cq_ else hashes.get((hsh,12), '<....>')
        cb = call_58(c58)
        (ca, cb) = (cb, ca) if swp else (ca, cb)
        return (ca, cb, ('', '', 'RRR', 'RR73', '73')[rrr])
    elif i3 == 5:
        return ('EU VHF','not','implemented')

def call_58(call_int):
    call = ""
    chars = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"
    for i in range(12):
        call = chars[call_int % 38] + call
        call_int = call_int // 38
    call =  call.strip()
    hashes[(ihashcall(call, 22), 22)] = call
    hashes[(ihashcall(call, 12), 12)] = call
    hashes[(ihashcall(call, 10), 10)] = call
    return call

def call_28(call_int, i3):
    def get_table_7(call_int):
        table_7 = {'DE':(0,0),'QRZ':(1,1),'CQ':(2,2), 'CQ nnn':(3,1002),'CQ x':(1004,1029),
                   'CQ xx':(1031,1731),'CQ xxxx':(21443,532443),'hash':(2063592,2063592+4194303)}
        for ct, (lo, hi) in table_7.items():
            if lo <= call_int <= hi:
                return ct        
    from string import ascii_uppercase as ltrs, digits as digs
    call_fields = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                    (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
    portable_rover = call_int & 1
    call_int >>= 1
    t7 = get_table_7(call_int)
    if t7 is not None:
        return t7 if t7 != 'hash' else hashes.get((call_int - 2063592, 22), '<....>')
    call_int -= (2063592 + 4194304)
    chars = []
    for alphabet, div in call_fields:
        idx, call_int = divmod(call_int, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    if portable_rover:
        call = call + ('/P' if i3 == 2 else '/R')
    hashes[(ihashcall(call, 22), 22)] = call
    hashes[(ihashcall(call, 12), 12)] = call
    hashes[(ihashcall(call, 10), 10)] = call
    return call
    
def ihashcall(call, m):
    chars = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"
    call = (call + "          ")[:11]
    x = 0
    for c in call[0:11]:
        x = 38*x + chars.find(c)
        x = x & ((int(1) << 64) - 1)
    x = x & ((1 << 64) - 1)
    x = x * 47055833459
    x = x & ((1 << 64) - 1)
    x = x >> (64 - m)
    return x

def decode_grid(grid_int):
    g15 = grid_int & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        return chr(65+a) + chr(65+b) + str(c) + str(d)
    r = g15 - 32400
    if r <= 4:
        return ('', '', 'RRR', 'RR73', '73')[r]
    snr = r - 35
    ir = grid_int >> 15
    prefix = 'R' if ir else ''
    return prefix + f"{snr:+03d}"
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
import warnings
warnings.filterwarnings("error")

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

#============== AUDIO IN ===========================================================
class AudioIn:
    def __init__(self, max_freq, wav_files = None):
        self.fft_len = int(BPT * SAMP_RATE // SYM_RATE)
        fft_out_len = self.fft_len // 2 + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_in = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_window = fft_window=np.hanning(self.fft_len).astype(np.float32)
        self.hops_per_cycle = HOPS_PER_CYCLE
        self.hops_per_grid = 2 * HOPS_PER_CYCLE
        self.dt = T_CYC / HOPS_PER_CYCLE
        self.df = max_freq / (self.nFreqs - 1)
        self.dBgrid_main = np.ones((self.hops_per_grid, self.nFreqs), dtype = np.float32)
        self.wav_files = wav_files
        self.dBgrid_main_ptr = 0

    def start_wav_load(self):
        threading.Thread(target = self.load_wavs, args =(self.wav_files,)).start()
        self.dBgrid_main_ptr = 0

    def load_wavs(self, wav_paths, hop_dt = 1 / (SYM_RATE * HPS) - 0.0014):
        samples_perhop = int(SAMP_RATE / (SYM_RATE * HPS))
        for wav_path in wav_paths:
            wf = wave.open(wav_path, "rb")
            hoptimes = []
            th = time.time()
            frames = wf.readframes(samples_perhop)
            while frames:
                delay = hop_dt - (time.time()-th)
                if(delay>0): time.sleep(delay)
                th = time.time()
                hoptimes.append(th)
                self._callback(frames, None, None, None)
                frames = wf.readframes(samples_perhop)
            wf.close()
            deltas = np.diff(hoptimes)
            print(f"[Receiver] read wav file with hop mean = {1000*np.mean(deltas):6.2f}ms, sd =  {1000*np.std(deltas):6.2f}ms")
            
    def start_streamed_audio(self, input_device_idx):
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = SAMP_RATE, input = True, input_device_index = input_device_idx,
            frames_per_buffer = int(SAMP_RATE / (SYM_RATE * HPS)), stream_callback=self._callback,)
        self.stream.start_stream()
        self.sync_pointer_to_wall_clock()

    def sync_pointer_to_wall_clock(self):
        if self.wav_files is None:
            self.dBgrid_main_ptr = int(time.time() * SYM_RATE * HPS) % HOPS_PER_GRID
       
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
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        np.multiply(self.audio_buffer, self.fft_window, out=self.fft_in)
        z = np.fft.rfft(self.fft_in)[:self.nFreqs]
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        self.dBgrid_main[self.dBgrid_main_ptr, :] = 10*np.log10(p)
        self.dBgrid_main_ptr = (self.dBgrid_main_ptr + 1) % self.hops_per_grid
        return (None, pyaudio.paContinue)


#============== CANDIDATE ===========================================================

from dataclasses import dataclass
from dataclasses import field

@dataclass(slots=True)
class Candidate:
    cyclestart: tuple
    f0_idx: int
    llr: np.ndarray = field(default_factory=lambda: np.empty(0))
    snr: float = -30
    dt: float = 0
    h0_idx: int = 0
    sync_score: float = 0
    demap_started: float = 0.0
    fHz: int = 0
    llr_sd: float = 0.0
    ncheck0: int = 99
    ncheck: int = 99
    n_its: int = 0
    llr_sd: float = 0
    decode_path: str = ''
    msg_tuple: tuple = ('','','')
    msg: str = ''
    decode_completed: float = 0.0
    decoder: str = "PyFT8"

    def demap(self, dBgrid_main, target_params = (3.3, 3.7)):
        self.demap_started = time.time()
        freq_idxs = self.f0_idx + BASE_FREQ_IDXS
        hops = (self.h0_idx + BASE_PAYLOAD_HOPS) % HOPS_PER_GRID
        dBgrid = dBgrid_main[np.ix_(hops, freq_idxs)]
        pmax = np.max(dBgrid)
        self.snr = np.clip(int(pmax - np.min(dBgrid) - 58), -24, 24)
        p = np.clip(dBgrid - pmax, -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc))
        llr = llr.ravel() / 10
        self.llr_sd = int(0.5+100*np.std(llr))/100.0
        llr = target_params[0] * llr / (1e-12 + self.llr_sd)
        self.llr = np.clip(llr, -target_params[1], target_params[1])
          
    def decode(self):
        decode_started = time.time()
        if(self.llr_sd < LLR_SD_MIN):
            self.decode_completed = time.time()
            return
        ldpc_decoder = LdpcDecoder()
        self.ncheck = ldpc_decoder.calc_ncheck(self.llr)
        self.ncheck0 = self.ncheck
        if 0 < self.ncheck <= LDPC_CONTROL[0]:
            self.llr, self.ncheck, self.n_its = ldpc_decoder.decode(self.llr)                   
        if(self.ncheck == 0):
            bits91_int = 0
            for bit in (self.llr[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            if(bits77_int):
                self.msg_tuple = unpack(bits77_int)
                self.msg = self.validate(self.msg_tuple)
        self.decode_completed = time.time()

    def validate(self, msg_tuple):
        e = False
        # checking if this is needed after adding full table_7 info and branches on i3, n3
        #mt = msg_tuple
        #e = e or (' ' in mt[0].strip() and not mt[0].startswith('CQ'))
        #e = e or (' ' in mt[1].strip())
        if not e:
            return ' '.join(self.msg_tuple)
        
#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, audio_in, freq_range, on_decode, on_busy_profile = None, verbose = False):
        self.verbose = verbose
        self.curr_cycle = 0
        self.sample_rate = 12000
        self.audio_in = audio_in
        self.nFreqs = self.audio_in.nFreqs
        self.fbins_per_signal = 8 * BPT
        self.df = freq_range[1]/(self.audio_in.nFreqs - 1)
        self.dt = 1 / (HPS * SYM_RATE)
        self.f0_idxs = range(int(freq_range[0]/self.df),
                        min(self.audio_in.nFreqs - self.fbins_per_signal, int(freq_range[1]/self.df)))
        self.on_decode = on_decode
        self.on_busy_profile = on_busy_profile
        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def search(self, f0_idxs, cyclestart, sync_idx = 1):
        cands = []
        cycle_h0 = self.curr_cycle * HOPS_PER_CYCLE
        sync_idx_offs = sync_idx*36*HPS
        costas_nhops = 7*HPS
        edge_to_cent = BPT//2
        # search_hops covers all freqs, and hops as specified by H0_RANGE. data is needed 'costas hops' greater than max h0
        search_hops = self.audio_in.dBgrid_main[cycle_h0 + H0_RANGE[0]+sync_idx_offs: cycle_h0 + H0_RANGE[1]+sync_idx_offs + costas_nhops , edge_to_cent:]
        nh, nf = search_hops.shape
        arr = np.zeros((7, nh, nf))     # costas 'row' for a single symbol index, by main nhops, nfreqs
        for i in range(7):
            hopshift = i * HPS
            arr[i, :nh-hopshift, :] = search_hops[hopshift:, :]
        freq_stack = np.stack([np.roll(arr, -j * BPT, axis=2) for j in range(7)], axis=1) # 7x7 costas points by main nhops, nfreqs
        rows = np.arange(7)
        costas_vals = freq_stack[rows, COSTAS]  # 'wanted' costas points by main nhops, nfreqs
        masked = freq_stack.copy()              # copy for punching out wanted points
        masked[rows, COSTAS] = 0                # leave only 'unwanted' costas points by main nhops, nfreqs
        row_sum = (1/6)*masked.sum(axis=1)      # sum of 'unwanted' by main nhops, nfreqs
        row_scores = costas_vals - row_sum      # dB at costas index less sum(others) for each symbol in costas grid, by main nhops, nfreqs
        scores = row_scores.sum(axis=0)         # search scores by main nhops, nfreqs
        for f0_idx in f0_idxs:
            c = Candidate(cyclestart = cyclestart, f0_idx = f0_idx)
            h0_idx = int(np.argmax(scores[:nh-costas_nhops, f0_idx]))
            sync_score = float(scores[h0_idx, f0_idx])
            c.h0_idx, c.sync_score = h0_idx + cycle_h0 , sync_score
            c.dt = (c.h0_idx - cycle_h0) * self.dt - 0.7
            c.fHz = int(f0_idx * self.df)
            cands.append(c)
        return cands

    def get_busy_profile(self):
        from numpy.lib.stride_tricks import sliding_window_view
        h0 = 0 if self.curr_cycle == 0 else HOPS_PER_CYCLE+1    
        fbin_sum = np.sum(self.audio_in.dBgrid_main[h0:self.audio_in.dBgrid_main_ptr, :], axis = 0)
        windows = sliding_window_view(fbin_sum, 8*BPT)
        bp = windows.max(axis=1) 
        return bp, self.curr_cycle
        
    def manage_cycle(self):
        dashes = "======================================================"
        candidates = []
        duplicate_filter = set() 
        dBgrid_main_ptr_prev = 0
        base_pyld_hops = BASE_PAYLOAD_HOPS
        print("Rx running")
        ticker_cycle_rollover = Ticker(0)
        ticker_search_for_syncs = Ticker(H_SEARCH_1, timing_function = lambda: self.audio_in.dBgrid_main_ptr, cycle_length = HOPS_PER_CYCLE)
        self.audio_in.sync_pointer_to_wall_clock()
        while True:
            time.sleep(0.040)
            ptr = self.audio_in.dBgrid_main_ptr

            if ticker_cycle_rollover.ticked():                
                self.audio_in.sync_pointer_to_wall_clock()
                self.curr_cycle = int(((self.audio_in.dBgrid_main_ptr + 1) % HOPS_PER_GRID) / HOPS_PER_CYCLE)
        
            new_to_decode = []
            for c in candidates:
                ptr_rel_to_h0 = (ptr - c.h0_idx) % HOPS_PER_CYCLE
                if not (base_pyld_hops[0] <= ptr_rel_to_h0 <= base_pyld_hops[-1]) and not c.demap_started:
                    c.demap(self.audio_in.dBgrid_main)
                if c.llr_sd > 0 and not c.decode_completed:
                    new_to_decode.append(c)
                if c.msg:
                    key = c.cyclestart['string'] + " " + " ".join(c.msg)
                    if key not in duplicate_filter:
                        duplicate_filter.add(key)
                        self.on_decode(c)
            new_to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
            for c in new_to_decode[:55]:
                c.decode()

            if ticker_search_for_syncs.ticked():
                global_time_utils.tlog(f"[Cycle manager] start search at hop { self.audio_in.dBgrid_main_ptr}", verbose = self.verbose)
                cyclestart = global_time_utils.cyclestart(time.time())
                candidates = self.search(self.f0_idxs, cyclestart)
                if not self.on_busy_profile is None:
                    self.on_busy_profile(*self.get_busy_profile())
                global_time_utils.tlog(f"[Cycle manager] New spectrum searched -> {len(candidates)} candidates", verbose = self.verbose) 

