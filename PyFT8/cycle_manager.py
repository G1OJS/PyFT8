import threading
from collections import Counter
import numpy as np
import time
from PyFT8.audio import find_device, AudioIn
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder
from PyFT8.bitflipper import flip_bits
from PyFT8.osd import osd_decode_minimal
import pyaudio
import queue
import wave
import os

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
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb
        self.hop_start_lattitude = int(2 / self.dt)
        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self.h_search = self.hop_start_lattitude + self.nhops_costas
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.base_payload_hops = np.array([self.hops_persymb * s for s in self.sigspec.payload_symb_idxs])
        self.base_data_hops = np.array([self.hops_persymb * s for s in self.sigspec.data_symb_idxs])
        self.csync_flat = self.make_csync(sigspec)

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -1/(self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def sync(self, c, costas_block_index):
        p = self.audio_in.pgrid_main[:, c.f0_idx:c.f0_idx + self.fbins_per_signal]
        pnorm = p / np.max(p)
        block_off = 36 * costas_block_index * self.hops_persymb
        for h0_idx in range(block_off, block_off + self.hop_start_lattitude):
            sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat))
            test_sync = {'h0_idx':h0_idx - block_off, 'score':sync_score}
            if test_sync['score'] > c.sync['score']:
                c.sync = test_sync
        c.tsecs = c.sync['h0_idx'] * self.dt-0.7
        c.data_hops = c.sync['h0_idx'] + self.base_data_hops
        c.payload_hops = c.sync['h0_idx'] + self.base_payload_hops

    def search(self, freq_range, cyclestart_str):
        cands = []
        pgrid = self.audio_in.pgrid_main[:self.h_search,:]
        f0_idx_low = int(freq_range[0]/self.audio_in.fft_df)
        f0_idx_high = int(freq_range[1]/self.audio_in.fft_df)
        f0_idxs = range(f0_idx_low, np.min([f0_idx_high, pgrid.shape[1] - 24]))
        for f0_idx in f0_idxs:
            c = Candidate()
            c.f0_idx = f0_idx
            c.fine_freq_idxs = c.f0_idx + np.array(range(24))
            c.fHz = int((c.f0_idx + self.fbins_pertone // 2) * self.audio_in.fft_df)
            p = pgrid[:, c.fine_freq_idxs]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[c.fine_freq_idxs] += max_pwr
            c.base_payload_hops, c.base_data_hops = self.base_payload_hops, self.base_data_hops
            self.sync(c, 0)
            c.cyclestart_str = cyclestart_str            
            cands.append(c)
        return cands

class Candidate:
    def __init__(self):
        self.msg = None
        self.ldpc = LdpcDecoder()
        self.dedupe_key = ""
        self.pgrid_copy = np.zeros((1,1))
        self.hard_decode_started, self.demap_started, self.demap_completed, self.decode_completed, self.sync2_started = False, False, False, False, False
        self.sync = {'h0_idx':0, 'score':0}
        self.ncheck, self.ncheck0 = 99, 99
        self.llr = None
        self.decode_path = ""
        self.codes_this_sync = ""
        self.llr0_quality = 0
        self.llr0_sd = 0
        self.snr, self.snr2 = -999, -999
        self.p_dB = None 
        
    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ";"
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        self.codes_this_sync = self.codes_this_sync + actor_code
        if(final):
            self.decode_completed = time.time()

    def _update_pgrid_copy(self, spectrum):
        available_hops = spectrum.audio_in.grid_main_ptr
        if(available_hops > self.pgrid_copy.shape[0]):
            self.pgrid_copy = spectrum.audio_in.pgrid_main[:available_hops, self.fine_freq_idxs].copy()
        
    def _get_llr(self, spectrum, hops, target_params = (3.3, 3.7)):
        centrebins = [t * spectrum.fbins_pertone for t in range(8)]
        p = self.pgrid_copy[hops, :][:, centrebins]
        p = np.clip(p, np.max(p)/1e8, None)
        p_dB = 10*np.log10(p)
        llra = np.max(p_dB[:, [4,5,6,7]], axis=1) - np.max(p_dB[:, [0,1,2,3]], axis=1)
        llrb = np.max(p_dB[:, [2,3,4,7]], axis=1) - np.max(p_dB[:, [0,1,5,6]], axis=1)
        llrc = np.max(p_dB[:, [1,2,6,7]], axis=1) - np.max(p_dB[:, [0,3,4,5]], axis=1)
        llr0 = np.column_stack((llra, llrb, llrc))
        llr0 = llr0.ravel()
        llr0_sd = np.std(llr0)
        snr = int(np.clip(np.max(p_dB) - 107, -24, 24))
        if (llr0_sd > 0.001):
            llr0 = target_params[0] * llr0 / llr0_sd
            llr0 = np.clip(llr0, -target_params[1], target_params[1])
            llr0_quality =  np.sum(np.abs(llr0)) * 3*(79-21)/len(llr0)
        return (llr0, llr0_sd, llr0_quality, p_dB, snr)

    def hard_decode(self, spectrum, min_snr_metric = -90):
        self.hard_decode_started = True
        self._update_pgrid_copy(spectrum)
        p = self.pgrid_copy[self.data_hops,:]
        max_p = np.max(p, axis = 1)
        sum_p = np.sum(p, axis = 1)
        if(np.mean(max_p / sum_p) > min_snr_metric):
            maxpwr_idxs = np.argmax(p, axis = 1)
            symbols = np.array([int(m / spectrum.fbins_pertone) for m in maxpwr_idxs])
            bits = [[[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]][tone] for tone in symbols]
            bits = np.array(bits).flatten().tolist()
            bits = bits[:87]+bits[21+87:21+91]
            self.llr0, self.llr0_sd, self.llr0_quality, self.p_dB, self.snr = self._get_llr(spectrum, self.data_hops)
            if(check_crc_codeword_list(bits)):
                self.msg = FT8_unpack(bits[:77])
            if(self.msg):
                self.ncheck0, self.ncheck = 0, 0
                self._record_state("H")
                self._record_state("C", final = True)
       
    def demap(self, spectrum, min_llr0_quality = 410):
        self.demap_started = True
        self._update_pgrid_copy(spectrum)
        self.llr0, self.llr0_sd, self.llr0_quality, self.p_dB, self.snr = self._get_llr(spectrum, self.payload_hops)
        self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
        self.llr = self.llr0.copy()
        self.ncheck = self.ncheck0
        self.demap_completed = time.time()
        qual_too_low = self.llr0_quality < min_llr0_quality
        self._record_state("I", final = qual_too_low)

    def progress_decode(self, nc_thresh_bitflip = 28, nc_max_ldpc = 30,
                      iters_max_ldpc = 6, osd_qual_range = [410,470]):
        
        if(self.ncheck == 0):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if check_crc_codeword_list(codeword_bits):
                self.msg = FT8_unpack(codeword_bits)
            if self.msg:
                self._record_state("C", final = True)
            else:
                self._record_state("X", final = True)
            return

        if self.ncheck > nc_thresh_bitflip and not "A" in self.codes_this_sync:  
            self.llr, self.ncheck = flip_bits(self.llr, self.ncheck, width = 50, nbits=1, keep_best = True)
            self._record_state("A")
            return
        if nc_max_ldpc > self.ncheck > 0 and not self.codes_this_sync.count("L") > iters_max_ldpc:  
            self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
            self._record_state("L")
            return       
        if(osd_qual_range[0] < self.llr0_quality < osd_qual_range[1] and not "O" in self.codes_this_sync):
            reliab_order = np.argsort(np.abs(self.llr))[::-1]
            codeword_bits = osd_decode_minimal(self.llr0, reliab_order, Ls = [30,20,2])
            if check_crc_codeword_list(codeword_bits):
                self.llr = np.array([1 if(b==1) else -1 for b in codeword_bits])
                self.ncheck = 0
            self._record_state("O")
            return

        self._record_state("_", final = True)

class Cycle_manager():
    def __init__(self, sigspec, onSuccess, onOccupancy, audio_in_wav = None, test_speed_factor = 1.0, 
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200,3100], max_cycles = 5000, onCandidateRollover = None, verbose = False,
                 hard_decoding = {'allowed':True, 'on_sync2':False}):
        self.hard_decoding = hard_decoding
        self.spectrum = Spectrum(sigspec, 12000, freq_range[1], 3, 3)
        self.running = True
        self.verbose = verbose
        self.freq_range = freq_range
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.global_time_offset = 0
        self.global_time_multiplier = test_speed_factor
        self.cands_list = []
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
        
    def manage_cycle(self):
        cycle_searched = True
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
                cycle_searched = False
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
                n_unprocessed = len([c for c in self.cands_list if not "#" in c.decode_path])
                if(n_unprocessed and self.verbose):
                    self.tlog(f"[Cycle manager] {n_unprocessed} unprocessed candidates detected")
                if(self.onCandidateRollover and cycle_counter > 1):
                    self.onCandidateRollover(self.cands_list)
                self.cands_list = self.new_cands

            if(self.hard_decoding['allowed']):
                data_hops_filled = [c for c in self.cands_list if self.spectrum.audio_in.grid_main_ptr > c.data_hops[-1]]
                to_hard_decode = [c for c in data_hops_filled if not c.decode_completed
                                    and (self.hard_decoding['on_sync2'] or not c.sync2_started)]
                for c in to_hard_decode:
                    if not c.hard_decode_started:
                        c.hard_decode(self.spectrum)

            to_demap = [c for c in self.cands_list if (self.spectrum.audio_in.grid_main_ptr > c.payload_hops[-1]) and not c.decode_completed]
            for c in to_demap:
                if(not c.demap_started):
                    c.demap(self.spectrum)

            to_progress_decode = [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            to_progress_decode.sort(key = lambda c: -c.llr0_quality) # in case of emergency (timeouts) process best first
            for c in to_progress_decode[:25]:
                c.progress_decode()

            to_try_sync_2 = [c for c in self.cands_list if not c.msg and c.decode_completed]
            for c in to_try_sync_2:
                if not c.sync2_started:
                    c.sync2_started = True
                    h0_0 = c.sync['h0_idx']
                    self.spectrum.sync(c, 1)
                    if(c.sync['h0_idx'] != h0_0):
                        c.hard_decode_started, c.demap_started, c.demap_completed, c.decode_completed = False, False, False, False
                        c.codes_this_sync = ""
            
            with_message = [c for c in self.cands_list if c.msg]
            for c in with_message:
                c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                if(not c.dedupe_key in self.duplicate_filter or "Q" in c.decode_path):
                    self.duplicate_filter.add(c.dedupe_key)
                    c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
                    if(self.onSuccess): self.onSuccess(c)                   

            
