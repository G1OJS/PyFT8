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
from PyFT8.audio import AudioOut
import pyaudio
import queue
import wave
import os

params = {
'MIN_LLR0_SD': 5,
'BITFLIP_CONTROL': (28, 45),
'LDPC_CONTROL': (45, 5),
'OSD_CONTROL': [(13, 50), (6, 20)]
}

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
        self.h_search = self.hop_start_lattitude + self.nhops_costas + 36 * self.hops_persymb
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

    def sync(self, c):
        p = self.audio_in.pgrid_main[:, c.f0_idx:c.f0_idx + self.fbins_per_signal]
        pnorm = p / np.max(p)
        for costas_block_index in [0,1]:
            block_off = 36 * costas_block_index * self.hops_persymb
            for h0_idx in range(block_off, block_off + self.hop_start_lattitude):
                sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat))
                test_sync = {'h0_idx':h0_idx - block_off, 'score':sync_score, 'tsecs': (h0_idx - block_off) * self.dt-0.7}
                if test_sync['score'] > c.syncs[costas_block_index]['score']:
                    c.syncs[costas_block_index] = test_sync
        latest_h0 = np.max([c.syncs[0]['h0_idx'], c.syncs[1]['h0_idx']])
        c.last_data_hop = latest_h0 + self.sigspec.data_symb_idxs[-1] * self.hops_persymb
        c.last_payload_hop = latest_h0 + self.sigspec.payload_symb_idxs[-1] * self.hops_persymb

    def search(self, freq_range, cyclestart_str):
        cands = []
        pgrid = self.audio_in.pgrid_main[:self.h_search,:]
        f0_idx_low = int(freq_range[0]/self.audio_in.fft_df)
        f0_idx_high = int(freq_range[1]/self.audio_in.fft_df)
        f0_idxs = range(f0_idx_low, np.min([f0_idx_high, pgrid.shape[1] - 24]))
        for f0_idx in f0_idxs:
            c = Candidate()
            c.cyclestart_str = cyclestart_str  
            c.f0_idx = f0_idx
            c.fine_freq_idxs = c.f0_idx + np.array(range(24))
            c.fHz = int((c.f0_idx + self.fbins_pertone//2)  * self.audio_in.fft_df)
            p = pgrid[:, c.fine_freq_idxs]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[c.fine_freq_idxs] += max_pwr
            self.sync(c)
            cands.append(c)
        return cands

class Candidate:
    def __init__(self):
        self.msg = None
        self.ldpc = LdpcDecoder()
        self.available_hops = 0
        self.dedupe_key = ""
        self.demap_completed = False
        self.decode_completed = False
        s = {'h0_idx': 0, 'score': 0, 'tsecs': 0}
        self.syncs = [s,s]
        self.tsecs = 0
        self.decode_path = ""
        self.ncheck, self.ncheck0 = 99, 99
        self.llr, self.llr0 = None, None
        self.llr0_sd = 0
        self.snr = -30
        self.p_dB = None
     
    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ";"
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def _get_snr(self, p_dB):
        snr = int(np.clip(np.max(p_dB) - 107, -24, 24))
        return snr

    def _get_llr(self, spectrum, hops, target_params = (3.3, 3.7)):
        centrebins = [t * spectrum.fbins_pertone for t in range(8)]
        self.pgrid = spectrum.audio_in.pgrid_main[:, self.fine_freq_idxs]
        p = self.pgrid[hops, :][:, centrebins]
        pmax = np.max(p)
        if(pmax ==0):
            return (None, None, None, None)
        p /= pmax
        p = np.clip(p, 1e-8, 1.0)
        p_dB = 10*np.log10(p)
        llra = np.max(p_dB[:, [4,5,6,7]], axis=1) - np.max(p_dB[:, [0,1,2,3]], axis=1)
        llrb = np.max(p_dB[:, [2,3,4,7]], axis=1) - np.max(p_dB[:, [0,1,5,6]], axis=1)
        llrc = np.max(p_dB[:, [1,2,6,7]], axis=1) - np.max(p_dB[:, [0,3,4,5]], axis=1)
        llr0 = np.column_stack((llra, llrb, llrc))
        llr0 = llr0.ravel()
        snr = self._get_snr(p_dB)
        llr0_sd = np.std(llr0)
        if(llr0_sd > params['MIN_LLR0_SD']):
            llr0 = target_params[0] * llr0 / llr0_sd
        llr0 = np.clip(llr0, -target_params[1], target_params[1])
        return (llr0, llr0_sd, p_dB, snr)

    def demap(self, spectrum):
        demap0 = self._get_llr(spectrum, spectrum.base_payload_hops + self.syncs[0]['h0_idx'])
        demap1 = self._get_llr(spectrum, spectrum.base_payload_hops + self.syncs[1]['h0_idx'])
        demap_choice = 0 if demap0[1] > demap1[1] else 1
        self.llr0, self.llr0_sd, self.p_dB, self.snr = [demap0, demap1][demap_choice]
        self.tsecs = self.syncs[demap_choice]['tsecs']
        self.h0_idx = self.syncs[demap_choice]['h0_idx']
        if(self.llr0 is None):
            self._record_state("I", final = True)
            return
        if(self.llr0_sd < params['MIN_LLR0_SD']):
            self._record_state("I", final = True)
        else:
            self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
            self.ncheck = self.ncheck0
            self.llr = self.llr0.copy()
            self._record_state("I")

    def progress_decode(self):
        
        if(self.ncheck == 0):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if(np.sum(codeword_bits) == 0):
                self._record_state("0", final = True)
                return
            if check_crc_codeword_list(codeword_bits):
                self.msg = FT8_unpack(codeword_bits)
            if self.msg:
                self._record_state("C", final = True)
            else:
                self._record_state("X", final = True)
            return

        if self.ncheck >= params['BITFLIP_CONTROL'][0] and not "A" in self.decode_path:  
            self.llr, self.ncheck = flip_bits(self.llr, self.ncheck, width = params['BITFLIP_CONTROL'][0], nbits=1, keep_best = True)
            self._record_state("A")
            return
        if params['LDPC_CONTROL'][0] >= self.ncheck > 0 and not self.decode_path.count("L") > params['LDPC_CONTROL'][1]:  
            self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
            self._record_state("L")
            return
        for i in [0,1]:
            code = ['O','P'][i]
            if(self.llr0_sd < params['OSD_CONTROL'][i][0] and not code in self.decode_path):
                reliab_order = np.argsort(np.abs(self.llr))[::-1]
                codeword_bits = osd_decode_minimal(self.llr0, reliab_order, Order = 1, L = params['OSD_CONTROL'][i][1])
                if check_crc_codeword_list(codeword_bits):
                    self.llr = np.array([1 if(b==1) else -1 for b in codeword_bits])
                    self.ncheck = 0
                self._record_state(code)
                return
        
        self._record_state("_", final = True)

class Cycle_manager():
    def __init__(self, sigspec, onSuccess, onOccupancy, audio_in_wav = None, test_speed_factor = 1.0, 
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200,3100], max_cycles = 5000, onCandidateRollover = None, verbose = False):
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
        self.output_duplicate_filter = set()
        self.hops_percycle = self.spectrum.audio_in.hops_percycle
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
            self.tlog(f"[Cycle manager] Hop timings: mean = {m:.2f}ms, sd = {s:.2f}ms ({pc:5.1f}% symbol)")

    def check_for_tx(self):
        from PyFT8.FT8_encoder import pack_message
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
                    self.tlog(f"[Cycle manager] rollover detected at {self.cycle_time():.2f}")
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
                n_unprocessed = len([c for c in self.cands_list if not "#" in c.decode_path])
                if(self.verbose):
                    self.tlog(f"[Cycle manager] Search spectrum ...")
                    self.tlog(f"[Cycle manager] {n_unprocessed} unprocessed candidates detected")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.audio_in.fft_df)
                if(self.onCandidateRollover and cycle_counter > 1): self.onCandidateRollover(self.cands_list)
                self.cands_list = self.spectrum.search(self.freq_range, self.cyclestart_str(time.time()))
                self.output_duplicate_filter = set()
                
            to_demap = [c for c in self.cands_list if ( self.spectrum.audio_in.grid_main_ptr > c.last_payload_hop)
                                                       and not c.decode_completed and not c.demap_completed]
            for c in to_demap:
                c.demap(self.spectrum)
                c.demap_completed = True

            to_progress_decode = [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            to_progress_decode.sort(key = lambda c: (-c.llr0_sd, c.ncheck0)) # in case of emergency (timeouts) process best first
            for c in to_progress_decode[:25]:
                c.progress_decode()
            
            with_message = [c for c in self.cands_list if c.msg]
            for c in with_message:
                c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                if(not c.dedupe_key in self.output_duplicate_filter):
                    self.output_duplicate_filter.add(c.dedupe_key)
                    c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
                    if(self.onSuccess): self.onSuccess(c)





                    
