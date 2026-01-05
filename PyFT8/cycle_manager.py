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

eps = 1e-12

CHECK_VARS_6 = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
CHECK_VARS_7 = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)

def safe_pc(x,y):
    return 100*x/y if y>0 else 0

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

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

    def search(self, freq_range, cyclestart_str):
        cands = []
        n_close = 2
        f0_idxs = range(int(freq_range[0]/self.df),
                        min(self.nFreqs - self.fbins_per_signal, int(freq_range[1]/self.df)))
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
            c.cyclestart_str = cyclestart_str
            cands.append(c)
        return cands

class Candidate:

    def __init__(self):
        self.dedupe_key = ""
        self.sync_started, self.sync_completed = None, None
        self.demap_started, self.demap_completed = None, None
        self.decode_started, self.decode_completed = None, None
        self.decode_verified = False
        self.ncheck = 999
        self.ncheck_initial = 999
        self.ldpc_hist = []
        self.decode_history = ""
        self.msg = None
        self.snr = -999
        self.edges6, self.edges7 = None, None

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
        self.fade = np.std(pvt) / np.mean(pvt)
        pgrid_n = self.pgrid / pvt[:,None]
        llr0 = np.log(np.max(pgrid_n[:, [4,5,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.max(pgrid_n[:, [2,3,4,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,5,6]], axis=1))
        llr2 = np.log(np.max(pgrid_n[:, [1,2,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,3,4,5]], axis=1))
        self.llr = np.column_stack((llr0, llr1, llr2)).ravel()
        self.llr = 3.8 * self.llr / np.std(self.llr)

        llr0 = np.log(np.sum(pgrid_n[:, [4,5,6,7]], axis=1)) - np.log(np.sum(pgrid_n[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.sum(pgrid_n[:, [2,3,4,7]], axis=1)) - np.log(np.sum(pgrid_n[:, [0,1,5,6]], axis=1))
        llr2 = np.log(np.sum(pgrid_n[:, [1,2,6,7]], axis=1)) - np.log(np.sum(pgrid_n[:, [0,3,4,5]], axis=1))
        llrB = np.column_stack((llr0, llr1, llr2)).ravel()
        llrB = 3.8 * llrB / np.std(llrB)

        idx = np.abs(self.llr) < np.abs(llrB)
        self.llr[idx] = llrB[idx]

        self.calc_ncheck()
        self.ncheck_initial = self.ncheck
        self.decode_history = f"I{self.ncheck:02d},"
        self.demap_completed = time.time()

    def calc_ncheck(self):
        bits6 = self.llr[CHECK_VARS_6] > 0
        parity6 = np.sum(bits6, axis=1) & 1
        bits7 = self.llr[CHECK_VARS_7] > 0
        parity7 = np.sum(bits7, axis=1) & 1
        self.ncheck = int(np.sum(parity7) + np.sum(parity6))

    def _check_update(self, idx, edges, delta):
        if edges is None:
            edges = np.zeros(idx.shape, dtype=np.float32)
        v2c = self.llr[idx] - edges
        t    = np.tanh(-v2c)
        prod = np.prod(t, axis=1, keepdims=True) / t
        new  = prod / ((prod - 1.18) * (1.18 + prod))
        np.add.at(delta, idx, new - edges)
        return new
    
    def do_ldpc_iteration(self):
        delta = np.zeros_like(self.llr)
        self.edges6 = self._check_update(CHECK_VARS_6, self.edges6, delta)
        self.edges7 = self._check_update(CHECK_VARS_7, self.edges7, delta)
        self.llr += delta

    def flip_bits(self):
        nbits = 5
        flip_masks = ((np.arange(1 << nbits)[:, None] >> np.arange(nbits)) & 1).astype(bool)
        best_n = self.ncheck
        best_llr = self.llr.copy()
        ordered_llr_idxs = np.argsort(np.abs(self.llr))[:nbits]
        for mask in flip_masks:
            self.llr[ordered_llr_idxs[mask]] *= -1
            self.calc_ncheck()
            if self.ncheck < best_n:
                best_llr = self.llr.copy()
            else:
                self.llr[ordered_llr_idxs[mask]] *= -1
        self.llr = best_llr

    def progress_decode(self):
        self.decode_started = time.time()

        if(self.ncheck > 28):
            if(not "B" in self.decode_history):
                self.flip_bits()
                self.calc_ncheck()
                self.decode_history += f"B{self.ncheck:02d},"

        if(self.ncheck > 38):
            self.decode_completed = time.time()

        if(self.ncheck > 0):
            self.ldpc_hist.append(self.ncheck)
            self.do_ldpc_iteration()
            self.calc_ncheck()
            if(len(self.ldpc_hist) > 15):
                self.decode_completed = time.time()
            self.decode_history += f"L{self.ncheck:02d},"

        if(self.ncheck == 0):
            self.decode_completed = time.time()
            
    def verify_decode(self, duplicate_filter, onSuccess):
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
                if(onSuccess): onSuccess(self)
        self.decode_verified = True

    @property
    def info(self):
        return f"{self.sync_score:5.2f} {self.cyclestart_str[-2:]} {self.decode_history}" 

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200,3300], max_cycles = 5000, onCandidateRollover = None, verbose = False):
        
        HPS, BPT, MAX_FREQ, SAMPLE_RATE = 6, 3, 3500, 12000
        self.audio_in = AudioIn(SAMPLE_RATE, sigspec.symbols_persec, MAX_FREQ, HPS, BPT, on_fft = self.update_spectrum)
        self.spectrum = Spectrum(sigspec, SAMPLE_RATE, self.audio_in.nFreqs, MAX_FREQ, HPS, BPT)
        
        self.running = True
        self.verbose = verbose
        self.freq_range = freq_range
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.cands_list = []
        self.new_cands = []
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
        self.onCandidateRollover = onCandidateRollover

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

    def manage_cycle(self):
        cycle_searched = True
        cands_rollover_done = False
        cycle_counter = 0
        cycle_time_prev = 0
        to_demap = []
        while self.running:
            time.sleep(0.001)
            rollover = self.cycle_time() < cycle_time_prev 
            cycle_time_prev = self.cycle_time()

            if(rollover):
                cycle_counter +=1
                if(self.verbose):
                    self.tlog(f"\n[Cycle manager] rollover detected at {self.cycle_time():.2f}")
                if(cycle_counter > self.max_cycles):
                    self.running = False
                    break
                cycle_searched = False
                cands_rollover_done = False
                self.check_for_tx()
                self.spectrum.pgrid_fine_ptr = 0
                if not self.audio_started: self.start_audio()

            if (self.spectrum.pgrid_fine_ptr > self.spectrum.h_search and not cycle_searched):
                cycle_searched = True
                if(self.verbose): self.tlog(f"[Cycle manager] Search spectrum ...")
                self.new_cands = self.spectrum.search(self.freq_range, self.cyclestart_str(time.time()))
                if(self.verbose): self.tlog(f"[Cycle manager] Spectrum searched -> {len(self.new_cands)} candidates")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

            if(self.spectrum.pgrid_fine_ptr >= self.spectrum.h_demap-50 and not cands_rollover_done):
                cands_rollover_done = True
                if(self.onCandidateRollover): self.onCandidateRollover(self.cands_list)
                self.cands_list = self.new_cands

            if(self.spectrum.pgrid_fine_ptr >= self.spectrum.h_demap):
                to_demap = [c for c in self.cands_list
                                if (self.spectrum.pgrid_fine_ptr > c.payload_hop_idxs[-1]
                                and not c.demap_started)]
                for c in to_demap:
                    c.demap(self.spectrum)
               
            to_decode =  [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            if(to_decode):
                to_decode.sort(key = lambda c: c.ncheck)
                for c in to_decode[:10]:
                    c.progress_decode()

            to_verify = [c for c in self.cands_list if c.decode_completed and not c.decode_verified]
            for c in to_verify:
                c.verify_decode(self.duplicate_filter, self.onSuccessfulDecode)

                    
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
            

                       




                 
