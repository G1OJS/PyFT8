import threading
from collections import Counter
import numpy as np
import time
from .audio import find_device, AudioIn
from PyFT8.demapper import get_llr
from .FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder
from PyFT8.bitflipper import flip_bits
from PyFT8.osd import osd_decode_minimal
import pyaudio
import queue
import wave
import os

generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)
    
def safe_pc(x,y):
    return 100*x/y if y>0 else 0

class Spectrum:
    def __init__(self, sigspec, sample_rate, max_freq, hops_persymb, fbins_pertone):
        self.sigspec = sigspec
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.max_freq = max_freq
        self.hops_persymb = hops_persymb
        self.audio_in = AudioIn(self)
        self.nFreqs = self.audio_in.nFreqs
        self.dt = 1.0 / (self.sigspec.symbols_persec * self.hops_persymb) 
        self.df = max_freq / (self.nFreqs -1)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb
        self.hop_start_lattitude = int(1.9 / self.dt)
        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self.h_search = self.hop_start_lattitude + self.nhops_costas  + 36 * self.hops_persymb
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.csync_flat = self.make_csync(sigspec)

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -1/(self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def search(self, freq_range, cyclestart_str):
        cands = []
        f0_idxs = range(int(freq_range[0]/self.df),
                        min(self.nFreqs - self.fbins_per_signal, int(freq_range[1]/self.df)))
        pgrid = self.audio_in.pgrid_main[:self.h_search,:]
        block_off = 36 * self.hops_persymb
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            c = Candidate()
            syncs = []
            for iBlock in [0,1]:
                best = (0, f0_idx, -1e30)
                for h0_idx in range(block_off * iBlock, block_off * iBlock + self.hop_start_lattitude):
                    sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat))
                    test = (h0_idx - block_off * iBlock, f0_idx, sync_score)
                    if test[2] > best[2]:
                        best = test 
                syncs.append(best)
            c.record_possible_syncs(self, syncs)
            c.cyclestart_str = cyclestart_str            
            cands.append(c)
        return cands

class Candidate:

    def __init__(self):
        self.dedupe_key = ""
        self.demap_started, self.demap_completed = None, None
        self.decode_completed = None
        self.ncheck = None
        self.ncheck0 = None
        self.llr = None
        self.invoked_actors = set()
        self.decode_path = ""
        self.counters = [0]*10
        self.llr0_quality = 0
        self.msg = None
        self.snr = -999
        self.ldpc = LdpcDecoder()

    def record_possible_syncs(self, spectrum, syncs):
        hps, bpt = spectrum.hops_persymb, spectrum.fbins_pertone
        self.syncs = syncs
        self.f0_idx = syncs[0][1]
        self.freq_idxs = [self.f0_idx + bpt // 2 + bpt * t for t in range(spectrum.sigspec.tones_persymb)]
        self.fHz = int((self.f0_idx + bpt // 2) * spectrum.df)
        self.last_payload_hop = np.max([syncs[0][0], syncs[1][0]]) + hps * spectrum.sigspec.payload_symb_idxs[-1]
        
    def demap(self, spectrum, min_qual = 400):
        self.demap_started = time.time()
        
        h0, h1 = self.syncs[0][0], self.syncs[1][0]
        if(h0 == h1): h1 = h0 +1
        demap0 = get_llr(spectrum.audio_in.pgrid_main, h0, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        demap1 = get_llr(spectrum.audio_in.pgrid_main, h1, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        sync_idx =  0 if demap0[2] > demap1[2] else 1
        
        self.h0_idx = self.syncs[sync_idx][0]
        self.sync_score = self.syncs[sync_idx][2]
        self.dt = self.h0_idx * spectrum.dt-0.7

        demap = [demap0, demap1][sync_idx]
        self.llr0, self.llr0_sd, self.llr0_quality, self.pgrid, self.snr = demap
        self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
        self.llr = self.llr0.copy()
        self.ncheck = self.ncheck0

        quality_too_low = (self.llr0_quality < min_qual)
        self._record_state(f"I", self.ncheck, final = quality_too_low)
        
        self.demap_completed = time.time()

    def progress_decode(self):
        final = False
        if(self.ncheck > 0):
            actor = self._invoke_actor()
            self.invoked_actors.add(actor)
            stalled = (actor == "_")
            self._record_state(actor, self.ncheck, final = stalled)
        if(self.ncheck == 0 or final):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if check_crc_codeword_list(codeword_bits):
                self.payload_bits = codeword_bits[:77]
                self.msg = FT8_unpack(self.payload_bits)
            if self.msg:
                self._record_state("C", 0, final = True)
            else:
                self._record_state("X", 0, final = True)

    def _record_state(self, actor_code, ncheck, final = False):
        self.ncheck = ncheck
        finalcode = "#" if final else ";"
        self.decode_path = self.decode_path + f"{actor_code}{ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()
        
    def _invoke_actor(self, nc_thresh_bitflip = 28, nc_max_ldpc = 35, iters_max_ldpc = 7, osd_qual_range = [400,450]):
        counter = 0
        if self.ncheck > nc_thresh_bitflip and not self.counters[counter] > 0:  
            self.llr, self.ncheck = flip_bits(self.llr, self.ncheck, width = 50, nbits=1, keep_best = True)
            self.counters[counter] += 1
            return "A"
        counter = 1
        if nc_max_ldpc > self.ncheck > 0 and not self.counters[counter] > iters_max_ldpc:  
            self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
            self.counters[counter] += 1
            return "L"
        counter = 2
        if(osd_qual_range[0] < self.llr0_quality < osd_qual_range[1] and not self.counters[counter] > 0):
            reliab_order = np.argsort(np.abs(self.llr))[::-1]
            codeword_bits = osd_decode_minimal(self.llr0, reliab_order, G, Ls = [50,20,3])
            if check_crc_codeword_list(codeword_bits):
                self.llr = np.array([1 if(b==1) else -1 for b in codeword_bits])
                self.ncheck = 0
            self.counters[counter] += 1
            return "O"
        return "_"

                
                
class Cycle_manager():
    def __init__(self, sigspec, onSuccess, onOccupancy, audio_in_wav = None, test_speed_factor = 1.0, 
                 input_device_keywords = None, output_device_keywords = None, dump_main_grid = False,
                 freq_range = [200,3100], max_cycles = 5000, onCandidateRollover = None, verbose = False):
        
        HPS, BPT, MAX_FREQ, SAMPLE_RATE = 3, 3, freq_range[1], 12000
        self.spectrum = Spectrum(sigspec, SAMPLE_RATE, MAX_FREQ, HPS, BPT)
        self.running = True
        self.verbose = verbose
        self.dump_main_grid = dump_main_grid
        self.freq_range = freq_range
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.global_time_offset = 0
        self.global_time_multiplier = test_speed_factor
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
        self.onCandidateRollover = onCandidateRollover
        if(not self.audio_in_wav):
            delay = self.spectrum.sigspec.cycle_seconds - self.cycle_time()
            self.tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)")

    def start_audio(self):
        self.audio_started = True
        if(self.audio_in_wav):
            self.spectrum.audio_in.start_wav(self.audio_in_wav, self.spectrum.dt/self.global_time_multiplier)
        else:
            self.spectrum.audio_in.start_live(self.input_device_idx, self.spectrum.dt)
     
    def tlog(self, txt):
        print(f"{self.cyclestart_str(time.time())} {self.cycle_time():5.2f} {txt}")

    def cyclestart_str(self, t):
        cyclestart_time = self.cycle_seconds * int(t / self.cycle_seconds)
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

    def cycle_time(self):
        return (time.time()*self.global_time_multiplier-self.global_time_offset) % self.cycle_seconds

    def analyse_hoptimes(self):
        if not any(self.spectrum.audio_in.hoptimes): return
        diffs = np.ediff1d(self.spectrum.audio_in.hoptimes)
        if(self.verbose):
            m = 1000*np.mean(diffs)
            s = 1000*np.std(diffs)
            pc = safe_pc(s, 1000/self.spectrum.sigspec.symbols_persec) 
            self.tlog(f"\n[Cycle manager] Hop timings: mean = {m:.2f}ms, sd = {s:.2f}ms ({pc:5.1f}% symbol)")
        
    def manage_cycle(self):
        cycle_searched = True
        cands_rollover_done = False
        cycle_counter = 0
        cycle_time_prev = 0
        to_demap = []
        if(self.audio_in_wav):
            self.global_time_offset = self.cycle_time()+0.5
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
                if(self.dump_main_grid):
                    import pickle
                    with open(self.cyclestart_str(time.time()-3)+"_dump.pkl","wb") as f:
                        pickle.dump(self.spectrum.audio_in.zgrid_main, f)
                cycle_searched = False
                cands_rollover_done = False
                self.check_for_tx()
                self.spectrum.audio_in.grid_main_ptr = 0
                self.analyse_hoptimes()
                self.spectrum.audio_in.hoptimes = []
                if not self.audio_started: self.start_audio()

            if (self.spectrum.audio_in.grid_main_ptr > self.spectrum.h_search and not cycle_searched):

                cycle_searched = True
                if(self.verbose): self.tlog(f"[Cycle manager] Search spectrum ...")
                self.new_cands = self.spectrum.search(self.freq_range, self.cyclestart_str(time.time()))
                if(self.verbose): self.tlog(f"[Cycle manager] Spectrum searched -> {len(self.new_cands)} candidates")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

                if(self.verbose): self.tlog(f"[Cycle manager] Candidate rollover")
                cands_rollover_done = True
                n_unprocessed = len([c for c in self.cands_list if not "#" in c.decode_path])
                if(n_unprocessed and self.verbose):
                    self.tlog(f"[Cycle manager] {n_unprocessed} unprocessed candidates detected")
                if(self.onCandidateRollover and cycle_counter >1):
                    self.onCandidateRollover(self.cands_list)
                self.cands_list = self.new_cands
                if(self.spectrum.audio_in.wav_finished):
                    self.running = False
                
            to_demap = [c for c in self.cands_list
                            if (self.spectrum.audio_in.grid_main_ptr > c.last_payload_hop
                            and not c.demap_started)]
            for c in to_demap:
                c.demap(self.spectrum)

            to_progress_decode = [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            to_progress_decode.sort(key = lambda c: -c.llr0_quality) # in case of emergency (timeouts) process best first
            for c in to_progress_decode[:25]:
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
    assert cand.ldpc.calc_ncheck(self.llr) == 0

                    
