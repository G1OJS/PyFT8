import threading
from collections import Counter
import numpy as np
import time
from .audio import find_device, AudioIn
from .FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc
import pyaudio
import queue
import wave
import os

with open('failures.csv', 'w') as f:
    f.write(f"\n")

eps = 1e-12

ldpc_NRW = [7,6,6,6,7,6,7,6,6,7,6,6,7,7,6,6,6,7,6,7,6,7,6,6,6,7,6,6,6,7,6,6,6,6,7,6,6,6,7,7,6,6,6,6,7,7,6,6,6,6,7,6,6,6,7,6,6,6,6,7,6,6,6,7,6,6,6,7,7,6,6,7,6,6,6,6,6,6,6,7,6,6,6]
ldpc_NM = -1 + np.array([ [4,5,6,7,8,6,5,9,10,11,12,13,8,14,15,1,16,17,11,45,8,18,19,20,2,21,22,16,23,19,20,14,3,19,7,12,13,24,25,20,21,35,14,4,1,26,52,7,23,26,2,27,18,6,28,9,22,3,31,12,5,2,15,10,23,11,29,30,10,22,28,28,1,17,51,21,16,3,9,15,18,25,17],[31,32,24,33,25,32,34,35,36,37,38,39,40,41,42,33,43,37,44,55,46,36,38,47,48,45,47,39,43,35,36,31,44,46,49,50,51,52,53,46,54,82,30,29,4,51,84,50,55,41,27,40,49,33,48,54,53,13,69,43,39,54,56,44,34,49,34,50,53,57,32,29,26,27,57,37,47,24,40,58,42,38,42],[59,60,61,62,63,64,65,66,67,67,68,69,70,71,59,72,73,74,75,64,71,76,77,70,74,78,58,62,79,59,63,79,80,81,58,61,64,76,69,65,77,133,83,68,52,56,110,81,67,77,41,56,55,85,70,63,68,48,133,66,75,86,87,82,71,88,87,60,66,85,72,84,45,89,98,73,76,30,90,60,79,65,75],[91,93,94,95,83,97,78,99,100,87,102,103,82,88,106,106,108,81,110,111,112,89,104,92,113,83,118,112,120,73,94,98,124,117,90,118,114,129,90,80,100,142,113,120,57,91,115,99,95,109,61,124,124,108,85,131,109,78,150,89,102,101,108,91,94,92,97,86,84,93,103,88,80,103,163,138,130,72,106,74,144,99,129],[92,115,122,96,93,126,98,139,107,101,105,149,104,102,123,107,141,109,121,130,119,113,116,138,128,117,127,134,131,110,136,132,127,135,100,119,118,148,101,120,140,171,125,134,86,122,145,132,172,141,62,125,141,116,105,147,121,95,155,97,136,135,119,111,127,142,147,137,112,140,132,117,128,116,165,152,137,104,134,111,146,122,170],[96,146,151,143,96,138,107,146,126,139,155,162,114,123,159,157,160,131,166,161,166,114,163,165,160,121,164,158,145,125,161,164,169,167,105,144,157,149,130,140,171,174,170,173,136,137,168,173,174,148,115,126,167,156,129,155,174,123,169,135,167,164,171,144,153,157,162,142,128,159,166,143,147,153,172,169,154,139,151,150,152,160,172],[153,0,0,0,148,0,154,0,0,158,0,0,145,156,0,0,0,154,0,173,0,143,0,0,0,151,0,0,0,161,0,0,0,0,168,0,0,0,156,170,0,0,0,0,152,168,0,0,0,0,133,0,0,0,158,0,0,0,0,159,0,0,0,149,0,0,0,162,165,0,0,150,0,0,0,0,0,0,0,163,0,0,0],])

ldpc_check_vars = np.full((83, 7), -1, dtype=np.int16)
ldpc_check_deg  = np.zeros(83, dtype=np.int8)
for m in range(83):
    v = ldpc_NM[:ldpc_NRW[m], m]
    ldpc_check_vars[m, :len(v)] = v
    ldpc_check_deg[m] = len(v)

def safe_pc(x,y):
    return 100*x/y if y>0 else 0

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

class Candidate:

    def __init__(self):
        self.deduped = False
        self.sync_started, self.sync_completed = None, None
        self.demap_started, self.demap_completed = None, None
        self.decode_started, self.decode_completed = None, None
        self.info_str = ""
        self.msg = None
        self.ncheck = 999

    def record_sync(self, spectrum, h0_idx, f0_idx, score):
        hps, bpt = spectrum.hops_persymb, spectrum.fbins_pertone
        self.payload_hop_idxs  = [h0_idx + hps* s for s in spectrum.sigspec.payload_symb_idxs]   
        self.freq_idxs = [f0_idx + bpt // 2 + bpt * t for t in range(spectrum.sigspec.tones_persymb)]
        self.f0_idx = f0_idx
        self.h0_idx = h0_idx
        self.sync_score = score
        self.dt = self.h0_idx * spectrum.dt-0.7
        self.fHz = int((self.f0_idx + bpt // 2) * spectrum.df)
                                   
    def demap(self, spectrum):
        self.demap_started = time.time()
        self.pgrid = spectrum.pgrid_fine[np.ix_(self.payload_hop_idxs, self.freq_idxs)]
        self.snr = int(np.clip(10 * np.log10(np.max(self.pgrid)) - 107, -24, 24))
        pvt = np.mean(self.pgrid, axis = 1)
        pgrid_n = self.pgrid / pvt[:,None]
        llr0 = np.log(np.max(pgrid_n[:, [4,5,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.max(pgrid_n[:, [2,3,4,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,5,6]], axis=1))
        llr = np.log(np.max(pgrid_n[:, [1,2,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,3,4,5]], axis=1))
        llr = np.column_stack((llr0, llr1, llr)).ravel()
        llr_sd = np.std(llr)
        self.fade = np.std(pvt) / np.mean(pvt)
        self.llr = 3.8 * llr / llr_sd
        self.ncheck =  self.get_ncheck()
        self.info_str = f"{self.ncheck:02d}; "
        self.demap_completed = time.time()

    def get_ncheck(self):
        llr_check = self.llr[ldpc_check_vars]
        valid = ldpc_check_vars != -1
        parity = (np.sum((llr_check > 0) & valid, axis=1) & 1) 
        return np.sum(parity)

    def do_ldpc_iteration(self):
        delta = np.zeros_like(self.llr)
        for m in range(83):
            deg = ldpc_check_deg[m]
            v = ldpc_check_vars[m, :deg]
            self.Lnm = self.llr[v] - self.Lmn[m, :deg]
            t = np.tanh(-self.Lnm)         
            prod = np.prod(t) / t                       
            new = prod / ((prod - 1.18) * (1.18 + prod))
            delta[v] += new - self.Lmn[m, :deg]
            self.Lmn[m, :deg] = new
        self.llr += delta

    def decode(self, duplicate_filter, onSuccess):
        self.decode_started = time.time()
        if(self.ncheck > 0):
            self.Lmn = np.zeros((83, 7), dtype=np.float32)        
            ncheck_profile = [99,35,20,18,18,18,12,12,10,10,8,6,6,6,0]
            for ncp in ncheck_profile:
                self.do_ldpc_iteration()
                self.ncheck = self.get_ncheck()
                self.info_str += f"{self.ncheck:02d},"
                if(self.ncheck == 0 or self.ncheck > ncp): break
        self.decode_completed = time.time()
        if(self.ncheck == 0 ):
            threading.Thread(target = self.process_decode, args = (duplicate_filter,onSuccess, ) ).start()

        if(self.ncheck > 0):
            with open('failures.csv', 'a') as f:
                f.write(f"{time.time()%15:5.2f},{self.info_str}\n")

    def process_decode(self, duplicate_filter, onSuccess):
        self.payload_bits = []
        decoded_bits = (self.llr > 0).astype(int).tolist()
        if any(decoded_bits[:77]):
            if check_crc(bitsLE_to_int(decoded_bits[0:91]) ):
                self.payload_bits = decoded_bits[:77]
        if(any(self.payload_bits)):
            self.msg = FT8_unpack(self.payload_bits)
            self.call_a, self.call_b, self.grid_rpt = self.msg[0], self.msg[1], self.msg[2]
            self.dedupe_key = self.cyclestart_str+" "+' '.join(self.msg)
            if(not self.dedupe_key in duplicate_filter):
                duplicate_filter.add(self.dedupe_key)
                onSuccess(self)

class Spectrum:
    def __init__(self, sigspec, sample_rate, nFreqs, max_freq, hops_persymb, fbins_pertone):
        self.sigspec = sigspec
        self.sample_rate = sample_rate
        self.nFreqs = nFreqs
        self.max_freq = max_freq
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        self.dt = 1.0 / (self.sigspec.symbols_persec * self.hops_persymb) 
        self.df = max_freq / (self.nFreqs -1)
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * self.hops_persymb)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb
        self.pgrid_fine = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.pgrid_fine_ptr = 0

        self.max_start_hop = int(1.9 / self.dt)
        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self.h_search = self.max_start_hop + self.nhops_costas 
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.lock = threading.Lock()
        self.csync_flat = self.make_csync(sigspec)

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -1/(sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def on_fft(self, z, t):
        p = z.real*z.real + z.imag*z.imag
        p = p[:self.nFreqs]
        with self.lock:
            self.pgrid_fine[self.pgrid_fine_ptr] = p
            self.pgrid_fine_ptr = (self.pgrid_fine_ptr + 1) % self.hops_percycle

    def search(self, f0 = 200, fn = 3100):
        cands = []
        n_close = 2
        f0_idxs = range(int(f0/self.df), min(self.nFreqs - self.fbins_per_signal, int(fn/self.df)))
        pgrid = self.pgrid_fine[:self.h_search,:]
        
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            best = (0, f0_idx, -1e30)
            c = Candidate()
            c.sync_started = time.time()
            for t0_idx in range(self.h_search - self.nhops_costas):
                test = (t0_idx, f0_idx, float(np.dot(pnorm[t0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat)))
                if test[2] > best[2]:
                    best = test
            c.record_sync(self, *best)
            c.sync_completed = time.time()

            neighbours = [cn for cn in cands[-n_close:] if c.f0_idx - cn.f0_idx < n_close] if len(cands)>n_close else []
            best_neighbour_score = np.max([cn.sync_score for cn in neighbours]) if len(neighbours) else 1e40
            if(c.sync_score > best_neighbour_score):
                for cand in neighbours:
                    cands.remove(cand)
            cands.append(c)
                
        return cands

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None, max_cycles = 5000, 
                 input_device_keywords = None, output_device_keywords = None, verbose = False):
        
        HPS, BPT, MAX_FREQ, SAMPLE_RATE = 6, 3, 3500, 12000
        self.audio_in = AudioIn(SAMPLE_RATE, sigspec.symbols_persec, MAX_FREQ, HPS, BPT, on_fft = self.update_spectrum)
        self.spectrum = Spectrum(sigspec, SAMPLE_RATE, self.audio_in.nFreqs, MAX_FREQ, HPS, BPT)
        
        self.running = True
        self.verbose = verbose
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.cands_list = []
        self.cands_lock = threading.Lock()
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        self.duplicate_filter = set()
        if(self.output_device_idx):
            from .audio import AudioOut
            self.audio_out = AudioOut
        self.audio_started = False
        self.cycle_seconds = sigspec.cycle_seconds

        threading.Thread(target=self.manage_cycle, daemon=True).start()
        delay = sigspec.cycle_seconds - self.cycle_time()
        self.tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)")
        self.cand_info = np.empty(self.spectrum.nFreqs, dtype= np.dtypes.StringDType())

    def update_spectrum(self, z, t):
        self.spectrum.on_fft(z, t)

    def start_audio(self):
        self.audio_started = True
        if(self.audio_in_wav):
            threading.Thread(target = self.audio_in.start_wav, args = (self.audio_in_wav, self.spectrum.dt), daemon=True).start()
        else:
            threading.Thread(target = self.audio_in.start_live, args=(self.input_device_idx,), daemon=True).start()
     
    def tlog(self, txt):
        print(f"{self.cyclestart_str(time.time())} {self.cycle_time():5.2f} {txt}")

    def cyclestart_str(self, t):
        cyclestart_time = self.cycle_seconds * int(t / self.cycle_seconds)
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

    def cycle_time(self):
        return time.time() % self.cycle_seconds

    def print_stats(self):
        if(self.verbose):
            sync_completed_times = [c.sync_completed for c in self.cands_list if c.sync_completed]
            demap_completed_times = [c.demap_completed for c in self.cands_list if c.demap_completed]
            decode_completed_times = [c.decode_completed for c in self.cands_list if c.decode_completed]
            def earliest_and_latest(arr): return f"first {np.min(arr)%15 :5.2f}, last {np.max(arr)%15 :5.2f}" if arr else ''
            self.tlog(f"[Cycle manager] sync_completed:   {len(sync_completed_times)} ({earliest_and_latest(sync_completed_times)})")
            self.tlog(f"[Cycle manager] demap_completed: {len(demap_completed_times)} ({earliest_and_latest(demap_completed_times)})")
            self.tlog(f"[Cycle manager] decode_completed:  {len(decode_completed_times)} ({earliest_and_latest(decode_completed_times)})")
        
    def manage_cycle(self):
        cycle_searched = True
        cycle_counter = 0
        cycle_time_prev = 0
        to_demap = []
        while self.running:
            time.sleep(0.001)
            rollover = self.cycle_time() < cycle_time_prev 
            cycle_time_prev = self.cycle_time()

            if(rollover):
                cycle_counter +=1
                self.tlog(f"\n[Cycle manager] rollover detected at {self.cycle_time():.2f}")
                if(cycle_counter > self.max_cycles):
                    self.running = False
                    break
                self.stats_printed = False
                cycle_searched = False
                self.check_for_tx()
                self.spectrum.pgrid_fine_ptr = 0
                if not self.audio_started: self.start_audio()

            if (self.spectrum.pgrid_fine_ptr > self.spectrum.h_search and not cycle_searched):
                cycle_searched = True
                self.print_stats()
                without_message = [c for c in self.cands_list if not c.msg]
                for c in without_message:
                    self.cand_info[c.f0_idx] = f" {c.sync_score:5.2f}; {c.info_str}"
                if(self.verbose): self.tlog(f"[Cycle manager] Search spectrum ...")
                new_cands = self.spectrum.search()
                if(self.verbose): self.tlog(f"[Cycle manager] Spectrum searched -> {len(new_cands)} candidates")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)
                with self.cands_lock:
                    self.cands_list = new_cands

            if(self.spectrum.pgrid_fine_ptr >= self.spectrum.h_demap):
                with self.cands_lock:
                    to_demap = [c for c in self.cands_list
                                if (self.spectrum.pgrid_fine_ptr > c.payload_hop_idxs[-1]
                                and not c.demap_started)]
                for c in to_demap:
                    c.demap(self.spectrum)
                    c.cyclestart_str = self.cyclestart_str(time.time())
                    if(c.ncheck == 0):
                        c.decode(self.duplicate_filter, self.onSuccessfulDecode)

            if not len(to_demap):
                with self.cands_lock:
                    to_decode =  [c for c in self.cands_list if c.demap_completed and not c.decode_started]
                if(to_decode):
                    c = to_decode[np.argmin([c.ncheck for c in to_decode])]
                    c.decode(self.duplicate_filter, self.onSuccessfulDecode)

    def check_for_tx(self):
        from .FT8_encoder import pack_message
        tx_msg_file = 'PyFT8_tx_msg.txt'
        if os.path.exists(tx_msg_file):
            if(not self.output_device_idx):
                self.tlog("[Tx] Tx message file found but no output device specified")
                return
            with open(tx_msg_file, 'r') as f:
                tx_msg = f.readline().strip()
                tx_freq = f.readline().strip()
            tx_freq = int(tx_freq) if tx_freq else 1000    
            self.tlog(f"[TX] transmitting {tx_msg} on {tx_freq} Hz")
            os.remove(tx_msg_file)
            c1, c2, grid_rpt = tx_msg.split()
            symbols = pack_message(c1, c2, grid_rpt)
            audio_data = self.audio_out.create_ft8_wave(self, symbols, f_base = tx_freq)
            self.audio_out.play_data_to_soundcard(self, audio_data, self.output_device_idx)
            self.tlog("[Tx] done transmitting")
            

                       




                 
