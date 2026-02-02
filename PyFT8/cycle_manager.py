import threading
from collections import Counter
import numpy as np
import time
from PyFT8.audio import find_device, AudioIn
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder
from PyFT8.osd import osd_decode_minimal
import pyaudio
import queue
import wave
import os

params = {
'MIN_LLR0_SD': 0.5,                # global minimum llr_sd
'BITFLIP_CONTROL': (28, 50),        # min ncheck0, nBits
'LDPC_CONTROL': (45, 7, 5),         # max ncheck0, 
'OSD_CONTROL': (0.5, 1.5, [30,20,2]) # min llr_sd, max llr_sd, L(order)
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

    def get_syncs(self, f0_idx, pnorm):
        syncs = []
        for iBlock in [0,1]:
            best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
            block_off = 36 * self.hops_persymb * iBlock
            for h0_idx in range(block_off, block_off + self.hop_start_lattitude):
                sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas ,  :].ravel(), self.csync_flat))
                test_sync = {'h0_idx':h0_idx - block_off, 'score':sync_score, 'dt': (h0_idx - block_off) * self.dt-0.7}
                if test_sync['score'] > best_sync['score']:
                    best_sync = test_sync 
            syncs.append(best_sync)
        return syncs

    def search(self, f0_idxs, cyclestart_str, cycle_counter):
        cands = []
        pgrid = self.audio_in.pgrid_main[:self.h_search,:]
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            c = Candidate()
            c.cycle_counter = cycle_counter
            c.f0_idx = f0_idx
            c.syncs = self.get_syncs(f0_idx, pnorm)
            hps, bpt = self.hops_persymb, self.fbins_pertone
            c.freq_idxs = [c.f0_idx + bpt // 2 + bpt * t for t in range(self.sigspec.tones_persymb)]
            c.fHz = int((c.f0_idx + bpt // 2) * self.df)
            c.last_payload_hop = np.max([c.syncs[0]['h0_idx'], c.syncs[1]['h0_idx']]) + hps * self.sigspec.payload_symb_idxs[-1]
            c.cyclestart_str = cyclestart_str            
            cands.append(c)
        return cands

class Candidate:

    def __init__(self):
        self.dedupe_key = ""
        self.demap_started, self.demap_completed, self.decode_completed = None, None, None
        self.bitflip_done = False
        self.osd_done = False
        self.n_ldpc = 0
        self.dt = 0
        self.fHz = 0
        self.ncheck, self.ncheck0 = 99, 99
        self.llr0_sd = 0
        self.llr = []
        self.llr0 = []
        self.cycle_counter = 0
        self.cyclestart_str = ""
        self.decode_path = ""
        self.msg = ''
        self.snr = -30
        self.ldpc = LdpcDecoder()

    def _flip_bits(self, llr, ncheck, width, nbits, keep_best = False):
        import itertools
        cands = np.argsort(np.abs(llr))
        idxs = cands[:nbits]
        
        best = {'llr':llr.copy(), 'nc':ncheck}
        for k in range(1, width + 1):
            for comb in itertools.combinations(range(len(idxs)), k):
                llr[idxs[list(comb)]] *= -1
                n = self.ldpc.calc_ncheck(llr)
                if n < best['nc']:
                    best = {'llr':llr.copy(), 'nc':n}
                    if n == 0:
                        return best['llr'], 0
                if n >= best['nc'] or not keep_best:
                    llr[idxs[list(comb)]] *= -1
        return best['llr'], best['nc']

    def _get_llr(self, pgrid_main, h0_idx, hps, freq_idxs, payload_symb_idxs, target_params = (3.3, 3.7)):
        hops = np.array([h0_idx + hps* s for s in payload_symb_idxs])
        praw = pgrid_main[np.ix_(hops, freq_idxs)]
        pclip = np.clip(praw, np.max(praw)/1e8, None)
        pgrid = np.log10(pclip)
        llra = np.max(pgrid[:, [4,5,6,7]], axis=1) - np.max(pgrid[:, [0,1,2,3]], axis=1)
        llrb = np.max(pgrid[:, [2,3,4,7]], axis=1) - np.max(pgrid[:, [0,1,5,6]], axis=1)
        llrc = np.max(pgrid[:, [1,2,6,7]], axis=1) - np.max(pgrid[:, [0,3,4,5]], axis=1)
        llr0 = np.column_stack((llra, llrb, llrc))
        llr0 = llr0.ravel()
        llr0_sd = np.std(llr0)
        snr = int(np.clip(10*np.max(pgrid) - 107, -24, 24))
        if (llr0_sd > 0.001):
            llr0 = target_params[0] * llr0 / llr0_sd
            llr0 = np.clip(llr0, -target_params[1], target_params[1])
        return (llr0, llr0_sd, pgrid, snr)        
        
    def demap(self, spectrum):
        self.demap_started = time.time()
        
        h0, h1 = self.syncs[0]['h0_idx'], self.syncs[1]['h0_idx']
        if(h0 == h1): h1 = h0 +1
        demap0 = self._get_llr(spectrum.audio_in.pgrid_main, h0, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        demap1 = self._get_llr(spectrum.audio_in.pgrid_main, h1, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        sync_idx =  0 if demap0[1] > demap1[1] else 1
        
        self.h0_idx = self.syncs[sync_idx]['h0_idx']
        self.sync_score = self.syncs[sync_idx]['score']
        self.dt = self.syncs[sync_idx]['dt']

        demap = [demap0, demap1][sync_idx]
        self.p_dB = 10*demap[2]
        self.llr0, self.llr0_sd, self.pgrid, self.snr = demap
        self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
        self.llr = self.llr0.copy()
        self.ncheck = self.ncheck0

        quality_too_low = (self.llr0_sd < params['MIN_LLR0_SD'])
        self._record_state(f"I", final = quality_too_low)
        
        self.demap_completed = time.time()

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ";"
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def progress_decode(self):
        if(self.ncheck > 0):
            if self.ncheck > params['BITFLIP_CONTROL'][0] and not self.bitflip_done:  
                self.llr, self.ncheck = self._flip_bits(self.llr, self.ncheck, width = 50, nbits=1, keep_best = True)
                self.bitflip_done = True
                self._record_state("A")

            if params['LDPC_CONTROL'][0] > self.ncheck > 0:
                for it in range(params['LDPC_CONTROL'][1]):
                    self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
                    self.n_ldpc += 1
                    self._record_state("L")
                    if(self.ncheck == 0):
                        break

            if(self.ncheck > 0 and params['OSD_CONTROL'][0] < self.llr0_sd < params['OSD_CONTROL'][1] and not self.osd_done):
                reliab_order = np.argsort(np.abs(self.llr))[::-1]
                codeword_bits = osd_decode_minimal(self.llr0, reliab_order, Ls = params['OSD_CONTROL'][2])
                if check_crc_codeword_list(codeword_bits):
                    self.llr = np.array([1 if(b==1) else -1 for b in codeword_bits])
                    self.ncheck = 0
                self.osd_done = True
                self._record_state("O")

        if(self.ncheck == 0):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if check_crc_codeword_list(codeword_bits):
                self.payload_bits = codeword_bits[:77]
                self.msg = FT8_unpack(self.payload_bits)
            if self.msg:
                self._record_state("C", final = True)
            else:
                self._record_state("X", final = True)
        else:
            self._record_state("_", final = True)


            
class Cycle_manager():
    def __init__(self, sigspec, onSuccess, onOccupancy, audio_in_wav = None, test_speed_factor = 1.0, 
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200,3100], max_cycles = 5000, onCandidateRollover = None, verbose = False):
        
        HPS, BPT, MAX_FREQ, SAMPLE_RATE = 3, 3, freq_range[1], 12000
        self.spectrum = Spectrum(sigspec, SAMPLE_RATE, MAX_FREQ, HPS, BPT)
        self.running = True
        self.verbose = verbose
        self.freq_range = freq_range
        self.f0_idxs = range(int(freq_range[0]/self.spectrum.df),
                        min(self.spectrum.nFreqs - self.spectrum.fbins_per_signal, int(freq_range[1]/self.spectrum.df)))
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

                self.new_cands = self.spectrum.search(self.f0_idxs, self.cyclestart_str(time.time()), cycle_counter)
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
            to_progress_decode.sort(key = lambda c: -c.llr0_sd) # in case of emergency (timeouts) process best first
            for c in to_progress_decode[:25]:
                c.progress_decode()

            with_message = [c for c in self.cands_list if c.msg]
            for c in with_message:
                c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                if(not c.dedupe_key in self.duplicate_filter):
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
                         
