import threading
import numpy as np
import wave
import time
from PyFT8.time_utils import global_time_utils
import os
import pyaudio

LLR_SD_MIN = 0.5
HPS = 4
BPT =2
SYM_RATE = 6.25
SAMP_RATE = 12000
T_CYC = 15
LDPC_CONTROL = (45, 12) 

t2h = HPS/0.16
H0_RANGE = [int(-1 *t2h), int(3.4 *t2h)]
H_SEARCH_0 = H0_RANGE[1] + 7 * HPS
H_SEARCH_1 = H0_RANGE[1] + 43 * HPS 

BASE_FREQ_IDXS = np.array([BPT // 2 + BPT * t for t in range(8)])
symbol_idxs = list(range(7, 36)) + list(range(43, 72))
BASE_PAYLOAD_HOPS = np.array([HPS * s for s in symbol_idxs])
LAST_BASE_PAYLOAD_HOP = BASE_PAYLOAD_HOPS[-1]
COSTAS = [3,1,4,0,6,5,2]
BASE_COSTAS_HOPS =  np.arange(7) * HPS
BASE_FREQ_IDXS = np.array([BPT // 2 + BPT * t for t in range(8)])
HOPS_PER_CYCLE = int(T_CYC * SYM_RATE * HPS)
HOPS_PER_GRID = 2 * HOPS_PER_CYCLE

def cycle_time():
    return time.time() % T_CYC

def cyclestart_str(t):
    cyclestart_time = T_CYC * int( t / T_CYC )
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

#=========== Unpacking functions ========================================
from string import ascii_uppercase as ltrs, digits as digs
CALL_FIELDS = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
CALL_TOKENS = ("DE", "QRZ", "CQ")
NCALL_TOKENS_PLUS_MAX22 = 2_063_592 + 4_194_304
GRID_RR73s = ('', '', 'RRR', 'RR73', '73')
FT8_MSG_FORMAT = (("i3", 3), ("grid", 16), ("callB",29), ("callA",29))

def get_fields(bits, fmt):
    out = {}
    for name, n in fmt:
        mask = (1 << n) - 1
        out[name] = bits & mask
        bits >>= n
    return out

def unpack(bits77):
    fields = get_fields(bits77, FT8_MSG_FORMAT)
    return (decode_call(fields["callA"]), decode_call(fields["callB"]), decode_grid(fields["grid"]))

def decode_call(call_int):
    portable = call_int & 1
    call_int >>= 1
    if call_int < 3:
        return CALL_TOKENS[call_int]
    call_int -= NCALL_TOKENS_PLUS_MAX22
    if call_int == 0:
        return '<...>'
    chars = []
    for alphabet, div in CALL_FIELDS:
        idx, call_int = divmod(call_int, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    return call + '/P' if portable else call

def decode_grid(grid_int):
    g15 = grid_int & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        return chr(65+a) + chr(65+b) + str(c) + str(d)
    r = g15 - 32400
    if r <= 4:
        return GRID_RR73s[r]
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
        self.hops_per_grid = 2 * HOPS_PER_CYCLE
        self.dBgrid_main = np.ones((self.hops_per_grid, self.nFreqs), dtype = np.float32)
        self.wav_files = wav_files
        self.dBgrid_main_ptr = 0

    def start_wav_load(self):
        threading.Thread(target = self.load_wavs, args =(self.wav_files,)).start()
        self.dBgrid_main_ptr = 0

    def load_wavs(self, wav_paths, hop_dt = 1 / (SYM_RATE * HPS) - 0.001):
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
        self.dBgrid_main_ptr = int(cycle_time() * SYM_RATE * HPS)
        self.stream.start_stream()
       
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
    cyclestart_str: str
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
        p = np.clip(dBgrid - np.max(dBgrid), -80, 0)
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
                self.msg = ' '.join(self.msg_tuple)
        self.decode_completed = time.time()
        


#============== RECEIVER ===========================================================
class Receiver():
    def __init__(self, audio_in, freq_range, on_decode, waterfall, verbose = True):
        self.verbose = verbose
        self.waterfall = waterfall
        self.sample_rate = 12000
        self.audio_in = audio_in
        self.nFreqs = self.audio_in.nFreqs
        self.fbins_per_signal = 8 * BPT
        self.df = freq_range[1]/(self.audio_in.nFreqs - 1)
        self.dt = 1 / (HPS * SYM_RATE)
        self.f0_idxs = range(int(freq_range[0]/self.df),
                        min(self.audio_in.nFreqs - self.fbins_per_signal, int(freq_range[1]/self.df)))
        self.on_decode = on_decode
        self.csync_flat = self.make_csync()
        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def make_csync(self):
        csync = np.full((len(COSTAS), 8), -1/7, np.float32)
        for sym_idx, tone in enumerate(COSTAS):
            csync[sym_idx, tone] = 1.0
            csync[sym_idx, len(COSTAS)] = 0
        return csync.ravel()

    def search(self, f0_idxs, cyclestart_str):
        cands = []
        cycle = int(self.audio_in.dBgrid_main_ptr / HOPS_PER_CYCLE)
        cycle_h0 = cycle * HOPS_PER_CYCLE
        for f0_idx in f0_idxs:
            freq_idxs = f0_idx + BASE_FREQ_IDXS
            c = Candidate(cyclestart_str = cyclestart_str, f0_idx = f0_idx)
            dB = self.audio_in.dBgrid_main[:, freq_idxs]
            dB = dB - np.max(dB)
            for h0_idx in range(H0_RANGE[0] + cycle_h0, H0_RANGE[1] + cycle_h0):
                sync_score = float(np.dot(dB[h0_idx + BASE_COSTAS_HOPS  + 36 * HPS ,  :].ravel(), self.csync_flat))
                if sync_score > c.sync_score:
                    c.h0_idx, c.sync_score = h0_idx, sync_score
            c.dt = c.h0_idx * self.dt - 0.7
            c.fHz = int((f0_idx + BPT // 2) * self.df)
            cands.append(c)
        return cands
        
    def manage_cycle(self):
        dashes = "======================================================"
        candidates = []
        duplicate_filter = set() 
        dBgrid_main_ptr_prev = 0
        base_pyld_hops = BASE_PAYLOAD_HOPS
        print("Rx running")
        search_last = -1e30
        while True:
            time.sleep(0.001)
            ptr = self.audio_in.dBgrid_main_ptr
            if(ptr != dBgrid_main_ptr_prev):
                dBgrid_main_ptr_prev = ptr

                new_to_decode = []
                for c in candidates:
                    ptr_rel_to_h0 = (ptr - c.h0_idx) % HOPS_PER_CYCLE
                    if not (base_pyld_hops[0] <= ptr_rel_to_h0 <= base_pyld_hops[-1]) and not c.demap_started:
                        c.demap(self.audio_in.dBgrid_main)
                    if c.llr_sd > 0 and not c.decode_completed:
                        new_to_decode.append(c)
                    if c.msg:
                        key = c.cyclestart_str + " " + " ".join(c.msg)
                        if key not in duplicate_filter:
                            duplicate_filter.add(key)
                            if self.waterfall:
                                self.waterfall.post_decode(c.h0_idx, c.f0_idx, c.msg)
                            self.on_decode(c)
                new_to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
                for c in new_to_decode[:55]:
                    c.decode()

                search = (ptr - H_SEARCH_1) % HOPS_PER_CYCLE
                if(search < search_last):
                    global_time_utils.tlog(f"[Cycle manager] start search at hop { self.audio_in.dBgrid_main_ptr}", verbose = self.verbose)
                    candidates = self.search(self.f0_idxs, global_time_utils.cyclestart_str(time.time()))
                    global_time_utils.tlog(f"[Cycle manager] New spectrum searched -> {len(candidates)} candidates", verbose = self.verbose) 
                search_last = search
                
        summarise_cycle() # for wav files that have just finished

#============= SIMPLE LIVE Rx-ONLY CODE =========================================================================

def on_decode(c):
    print(c.msg)

if __name__ == "__main__":
    from PyFT8.gui import Gui
    audio_in = AudioIn(3100)
    input_device_idx = audio_in.find_device(['Mic', 'CODEC'])
    gui = Gui(audio_in.dBgrid_main, 4, 2, lambda msg: print(msg))
    rx = Receiver(audio_in, [200, 3100], on_decode, gui)
    audio_in.start_streamed_audio(input_device_idx)
    print("Start rx")
    gui.plt.show()
                         
