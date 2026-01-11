import threading
import itertools
from collections import Counter
import numpy as np
import time
from .audio import find_device, AudioIn
from .FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.osd import osd_decode_minimal
import pyaudio
import queue
import wave
import os

eps = 1e-12
LLR_SHAPING = {'final_sd':3.5, 'clip':3.9}
LLR_QUALITY = {'abs_min':405, 'bitflip_range':[405,430], 'osd_range':[430, 455, 485]}
BITFLIPS = { 'width':40, 'max_flips':1}
STALL_CRITERIA = {'Max_its':10, "Max_same":2}

CHECK_VARS_6 = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
CHECK_VARS_7 = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)
         
generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)
    
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
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -1/(self.fbins_per_signal - self.fbins_pertone), np.float32)
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
            for t0_idx in range(self.h_search - self.nhops_costas):
                test = (t0_idx, f0_idx, float(np.dot(pnorm[t0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat)))
                if test[2] > best[2]:
                    best = test
            c.record_sync(self, *best)
            c.cyclestart_str = cyclestart_str            
            cands.append(c)

        for i, c in enumerate(cands):
            left = np.clip(i-2,0,len(cands))
            right = np.clip(i+3,0,len(cands))
            potential_neighbours = cands[left:i] + cands[i+1:right]
            c.neighbours = [n for n in potential_neighbours if np.abs(n.f0_idx - c.f0_idx) == 1]

        return cands

class Candidate:

    def __init__(self):
        self.dedupe_key = ""
        self.demap_started, self.demap_completed = None, None
        self.decode_completed = None
        self.decode_verified = False
        self.neighbours = None
        self.ncheck = None
        self.ncheck0 = None
        self.llr = None
        self.decode_path = ""
        self.ldpc_stall = (99,0)
        self.ldpc_iters = 0
        self.osd_runs = 0
        self.llr_quality = 0
        self.n_bitflip_calls = 0
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
        hops = np.array(self.payload_hop_idxs)
        freqs = self.freq_idxs
        p0 = spectrum.pgrid_fine[np.ix_(hops, freqs)]

        llr0 = np.log(np.max(p0[:, [4,5,6,7]], axis=1)) - np.log(np.max(p0[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.max(p0[:, [2,3,4,7]], axis=1)) - np.log(np.max(p0[:, [0,1,5,6]], axis=1))
        llr2 = np.log(np.max(p0[:, [1,2,6,7]], axis=1)) - np.log(np.max(p0[:, [0,3,4,5]], axis=1))

        llr = np.column_stack((llr0, llr1, llr2))
        llr = llr.ravel()
 
        llr_clipto = LLR_SHAPING['clip']
        self.llr = np.clip(LLR_SHAPING['final_sd'] * llr / np.std(llr), -llr_clipto, llr_clipto)

        s = np.sign(self.llr)
        self.llr_quality = np.sum(s * self.llr)
        self.ncheck = self.calc_ncheck(self.llr)
        self.ncheck0 = self.ncheck
        
        if(self.llr_quality < LLR_QUALITY['abs_min']):
            self.record_state(f">", self.ncheck, final = True)
        else:
            self.record_state("I", self.ncheck)

        
        self.pgrid = p0
        pmax = np.max(self.pgrid)
        self.snr = int(np.clip(10 * np.log10(pmax) - 107, -24, 24))
        self.demap_completed = time.time()

    def calc_ncheck(self, llr):
        bits6 = llr[CHECK_VARS_6] > 0
        self.parity6 = np.sum(bits6, axis=1) & 1
        bits7 = llr[CHECK_VARS_7] > 0
        self.parity7 = np.sum(bits7, axis=1) & 1
        return int(np.sum(self.parity7) + np.sum(self.parity6))

    def record_state(self, actor_code, ncheck, final = False):
        self.ncheck = ncheck
        finalcode = "#" if final else ""
        self.decode_path = self.decode_path + f"{finalcode}{actor_code}{ncheck:02d},"
        if(final):
            self.decode_completed = time.time()

    def _pass_messages(self, idx, edges, delta):
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
        self.edges6 = self._pass_messages(CHECK_VARS_6, self.edges6, delta)
        self.edges7 = self._pass_messages(CHECK_VARS_7, self.edges7, delta)
        self.llr += delta
        self.ncheck = self.calc_ncheck(self.llr)

    def flip_bits(self):
        bad6 = CHECK_VARS_6[self.parity6.astype(bool)] 
        bad7 = CHECK_VARS_7[self.parity7.astype(bool)] 
        bad_vars = np.concatenate([bad6.ravel(), bad7.ravel()])
        counts = np.bincount(bad_vars, minlength=len(self.llr))
        cands = np.argsort(counts)[::-1]
        idxs = cands[:BITFLIPS['width']]
        
        best = {'llr':self.llr.copy(), 'nc':self.ncheck}
        for k in range(1, BITFLIPS['max_flips'] + 1):
            for comb in itertools.combinations(range(len(idxs)), k):
                self.llr[idxs[list(comb)]] *= -1
                n = self.calc_ncheck(self.llr)
                if n < best['nc']:
                    best = {'llr':self.llr.copy(), 'nc':n}
                    if n == 0:
                        break
                else:
                    self.llr[idxs[list(comb)]] *= -1
        self.llr   = best['llr']
        self.ncheck = best['nc']
        
    def attempt_reduce_ncheck(self):

        if(self.ncheck >0 and self.n_bitflip_calls <1 and self.ldpc_iters > 1):
            bfrng = LLR_QUALITY['bitflip_range']
            if(self.llr_quality < bfrng[1] and self.llr_quality > bfrng[0]):
                self.flip_bits()
                self.n_bitflip_calls +=1
                return "B"

        if self.ncheck >0 and self.ldpc_iters <= STALL_CRITERIA['Max_its'] and self.ldpc_stall[1] <= STALL_CRITERIA['Max_same']:  
            self.do_ldpc_iteration()
            self.ldpc_iters += 1
            if(self.ncheck < self.ldpc_stall[0]):
                self.ldpc_stall = (self.ncheck, 0)
            else:
                self.ldpc_stall = (self.ldpc_stall[0], self.ldpc_stall[1]+1)
            return "L"
        
        if(self.ncheck >0 and self.osd_runs < 1):
            osdrng = LLR_QUALITY['osd_range']
            if(self.llr_quality>osdrng[0] and self.llr_quality < osdrng[2]):
                self.osd_runs +=1
                if(self.llr_quality < osdrng[1]):
                    code = "Q"
                    codeword_bits, metric = osd_decode_minimal(self.llr.copy(), G, order=1, L=30)
                else:
                    codeword_bits, metric = osd_decode_minimal(self.llr.copy(), G, order=2, L=6)
                    code = "QQ"
                if check_crc_codeword_list(codeword_bits):
                    llr = np.array([1 if(b==1) else -1 for b in codeword_bits])
                    ncheck = self.calc_ncheck(llr)
                    if(ncheck < self.ncheck):    
                        self.ncheck = ncheck
                        self.llr = llr
                return code

        return "_"

    def progress_decode(self):
        
        if(time.time() %15 > 11 and self.neighbours is not None):
            for n in self.neighbours:
                if(n.demap_completed):
                    if n.llr_quality > self.llr_quality:
                        self.record_state("D", self.ncheck, final = True)
                        return

        if(self.ncheck > 0):
            actor = self.attempt_reduce_ncheck()
            stalled = (actor == "_")
            self.record_state(actor, self.ncheck, final = stalled)

        if(self.ncheck == 0):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if check_crc_codeword_list(codeword_bits):
                self.payload_bits = codeword_bits[:77]
                self.msg = FT8_unpack(self.payload_bits)
            if self.msg:
                self.record_state("C", 0, final = True)
            else:
                self.record_state("X", 0, final = True)
                

class Cycle_manager():
    def __init__(self, sigspec, onSuccess, onOccupancy, audio_in_wav = None,
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200,3100], max_cycles = 5000, onCandidateRollover = None, verbose = False):
        
        HPS, BPT, MAX_FREQ, SAMPLE_RATE = 5, 3, freq_range[1], 12000
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
        self.onSuccess = onSuccess
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
                if(self.verbose): self.tlog(f"[Cycle manager] Candidate rollover")
                cands_rollover_done = True
                n_unprocessed = len([c for c in self.cands_list if not "#" in c.decode_path])
                if(n_unprocessed and self.verbose):
                    self.tlog(f"[Cycle manager] {n_unprocessed} unprocessed candidates detected")
                if(self.onCandidateRollover and cycle_counter >1):
                    self.onCandidateRollover(self.cands_list)
                self.cands_list = self.new_cands
                if(self.audio_in.wav_finished):
                    self.running = False

            if(self.spectrum.pgrid_fine_ptr >= self.spectrum.h_demap):
                to_demap = [c for c in self.cands_list
                                if (self.spectrum.pgrid_fine_ptr > c.payload_hop_idxs[-1]
                                and not c.demap_started)]
                for c in to_demap:
                    c.demap(self.spectrum)

            to_progress_decode = [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            to_progress_decode.sort(key = lambda c: -c.llr_quality) # in case of emergency (timeouts) process best first
            for c in to_progress_decode[:10]:
                c.progress_decode()

            with_message = [c for c in self.cands_list if c.msg]
            for c in with_message:
                c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                if(not c.dedupe_key in self.duplicate_filter or "Q" in c.decode_path):
                    self.duplicate_filter.add(c.dedupe_key)
                    c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
                    if(self.onSuccess): self.onSuccess(c)

                    
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
            
def check_G():
    u = np.random.randint(0, 2, size=91, dtype=np.uint8)
    c = (u @ G) & 1
    cand = Candidate()
    print(c)
    cand.llr = np.where(c == 1, +1.0, -1.0)
    print(cand.llr)
    assert cand.calc_ncheck(self.llr) == 0

                    
