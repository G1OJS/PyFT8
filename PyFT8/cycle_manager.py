import threading
from types import SimpleNamespace
import numpy as np
import time
from .audio import find_device, AudioIn
from .decode174_91_v7_0 import LDPC174_91
from .FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc
import pyaudio
import queue
import wave
import os
eps = 1e-12

ldpc = LDPC174_91()

def safe_pc(x,y):
    return 100*x/y if y>0 else 0

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

class StageProps:
    def __init__(self):
        self.started_time   = None
        self.completed_time = None
        self.success        = False
        self.result         = None      
        self.metrics        = None

    def start(self):
        self.started_time = time.time()

    def complete(self, *, success=False, result=None, metrics=None):
        self.completed_time = time.time()
        self.success = success
        self.result = result
        self.metrics = metrics        

    @property
    def has_started(self):
        return self.started_time is not None

    @property
    def has_completed(self):
        return self.completed_time is not None

    @property
    def is_in_progress(self):
        return self.has_started and not self.has_completed

class Pipeline:
    def __init__(self):
        self.sync = StageProps()
        self.demap = StageProps()
        self.decode = StageProps()
        self.unpack = StageProps()

class Candidate:
    next_id = 0

    def __init__(self):
        self.id = Candidate.next_id
        Candidate.next_id += 1

        self.pipeline = Pipeline()
        self.deduped = False



    def record_sync(self, spectrum, h0_idx, f0_idx, score):
        hps, bpt = spectrum.hops_persymb, spectrum.fbins_pertone
        payload_hop_idxs  = [h0_idx + hps* s for s in spectrum.sigspec.payload_symb_idxs]   
        freq_idxs = [f0_idx + bpt // 2 + bpt * t for t in range(spectrum.sigspec.tones_persymb)]
        self.pipeline.sync.complete(
            success=True,
            result=SimpleNamespace(score = score, f0_idx = f0_idx, h0_idx = h0_idx,
                                   payload_hop_idxs = payload_hop_idxs, freq_idxs = freq_idxs)
        )

    def demap(self, spectrum):
        self.pipeline.demap.start()
        payload_hop_idxs = self.pipeline.sync.result.payload_hop_idxs
        freq_idxs = self.pipeline.sync.result.freq_idxs
        pgrid = spectrum.pgrid_fine[np.ix_(payload_hop_idxs, freq_idxs)]
        pvt = np.mean(pgrid, axis = 1)
        pgrid_n = pgrid / pvt[:,None]
        llr0 = np.log(np.max(pgrid_n[:, [4,5,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.max(pgrid_n[:, [2,3,4,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,1,5,6]], axis=1))
        llr = np.log(np.max(pgrid_n[:, [1,2,6,7]], axis=1)) - np.log(np.max(pgrid_n[:, [0,3,4,5]], axis=1))
        llr = np.column_stack((llr0, llr1, llr)).ravel()
        llr_sd = np.std(llr)
        llr = 3.8 * llr / llr_sd
        llr_check = llr[ldpc.check_vars]
        valid = ldpc.check_vars != -1
        parity = (np.sum((llr_check > 0) & valid, axis=1) & 1) 
        self.ncheck_hist =  [np.sum(parity)]
        self.pipeline.demap.complete(success=True,
            result  = SimpleNamespace(llr = llr, ncheck = self.ncheck_hist[-1]),
            metrics = SimpleNamespace(pgrid = pgrid, pmax=np.max(pgrid),llr_sd=llr_sd))

    def find_llr_offset(self):
        offsets = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2.0,2.1]
        offsets = np.array(offsets + [-o for o in offsets])
        llrs_with_offsets = self.llr[:, ldpc.check_vars] + offsets[:, None]
        valid = ldpc.check_vars != -1
        parity = (np.sum((llrs_with_offsets > 0) & valid, axis=2) & 1)
        nchecks = np.sum(parity, axis=1)
        best_idx = np.argmin(nchecks)
        ncheck = nchecks[best_idx]
        if(ncheck < ncheck_hist[-1]):
            return offsets[best_idx], ncheck

    def decode(self, onSuccess):
        llr = self.pipeline.demap.result.llr
        offset = 0

        self.pipeline.decode.start()
        if(self.ncheck_hist[-1] > 0 and self.ncheck_hist[-1] < 25 ):
            llr, self.ncheck_hist = ldpc.decode(llr, self.ncheck_hist, max_iters = 8)

 #       if(self.ncheck_hist[-1] > 0 and self.ncheck_hist[-1] < 10):
 #           llr, self.ncheck_hist = ldpc.decode(llr, self.ncheck_hist, max_iters = 15)

        payload_bits = []
        if(self.ncheck_hist[-1] == 0):
            decoded_bits = (llr > 0).astype(int).tolist()
            if any(decoded_bits[:77]):
                if check_crc(bitsLE_to_int(decoded_bits[0:91]) ):
                    payload_bits = decoded_bits[:77]
                    
        self.pipeline.decode.complete(success = any(payload_bits), result = SimpleNamespace(payload_bits = payload_bits),
            metrics = SimpleNamespace(
                ncheck_hist = self.ncheck_hist,
                offset = offset,
                info_str = f"{offset:5.2f},{','.join([str(h) for h in self.ncheck_hist])};"
            )
        )
        if(self.pipeline.decode.success):
            onSuccess(self, self.pipeline.decode.result.payload_bits)

    @property
    def snr(self):
        pmax = self.pipeline.demap.metrics.pmax
        snr = 10 * np.log10(pmax) - 107
        return int(np.clip(snr, -24, 24))

class Spectrum:
    def __init__(self, sigspec):
        self.sigspec = sigspec
        self.sample_rate = 12000
        self.hops_persymb = 3
        self.fbins_pertone = 3
        self.max_freq = 3500
        self.dt = 1.0 / (self.sigspec.symbols_persec * self.hops_persymb) 
        self.FFT_len = int(self.fbins_pertone * self.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = self.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        self.df = self.max_freq / (self.nFreqs -1)
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * self.hops_persymb)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone

        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self._csync = np.full((self.sigspec.costas_len, self.fbins_per_signal), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*self.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb

        self.pgrid_fine = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.pgrid_fine_ptr = 0

        self.max_start_hop = int(1.9 / self.dt)
        self.h_search = self.max_start_hop + self.nhops_costas 
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.lock = threading.Lock()

    def cyclestart_str(self, t):
        cyclestart_time = self.sigspec.cycle_seconds * int(t / self.sigspec.cycle_seconds)
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

    def cycle_time(self):
        return time.time() % self.sigspec.cycle_seconds

    def on_fft(self, z, t):
        p = z.real*z.real + z.imag*z.imag
        p = p[:self.nFreqs]
        with self.lock:
            self.pgrid_fine[self.pgrid_fine_ptr] = p
            self.pgrid_fine_ptr = (self.pgrid_fine_ptr + 1) % self.hops_percycle

    def search(self):
        cands = []
        f0_idxs = range(self.nFreqs - self.fbins_per_signal)
        pgrid = self.pgrid_fine[:self.h_search,:]
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            best = (0, f0_idx, -1e30)
            for t0_idx in range(self.h_search - self.nhops_costas):
                test = (t0_idx, f0_idx, float(np.dot(pnorm[t0_idx + self.hop_idxs_Costas ,  :].ravel(), self._csync.ravel())))
                if test[2] > best[2]:
                    best = test
            c = Candidate()
            c.record_sync(self, *best)
            cands.append(c)
        return cands

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 ncheck_max = 35, max_cycles = 5000, 
                 input_device_keywords = None, output_device_keywords = None, verbose = False):
        self.running = True
        self.verbose = verbose
        self.ncheck_max = ncheck_max
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.cands_list = []
        self.cands_lock = threading.Lock()
        self.duplicate_filter = set()
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        self.stats_printed = False
        if(self.output_device_idx):
            from .audio import AudioOut
            self.audio_out = AudioOut
        self.sigspec = sigspec
        self.spectrum = Spectrum(sigspec)
        self.audio_started = False

        threading.Thread(target=self.manage_cycle, daemon=True).start()
        delay = self.sigspec.cycle_seconds - self.spectrum.cycle_time()
        self.tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)")

    def start_audio(self):
        self.audio_started = True
        audio_in = AudioIn(sample_rate=self.spectrum.sample_rate,
                    samples_perhop = int(self.spectrum.sample_rate /(self.sigspec.symbols_persec * self.spectrum.hops_persymb)),
                    fft_len=self.spectrum.FFT_len, fft_window=np.kaiser(self.spectrum.FFT_len, 20),
                    on_fft = self.spectrum.on_fft)
        if(self.audio_in_wav):
            threading.Thread(target = audio_in.start_wav, args = (self.audio_in_wav, self.spectrum.dt), daemon=True).start()
        else:
            threading.Thread(target = audio_in.start_live, args=(self.input_device_idx,), daemon=True).start()
     
    def tlog(self, txt):
        print(f"{self.spectrum.cyclestart_str(time.time())} {self.spectrum.cycle_time():5.2f} {txt}")

    def print_stats(self):
        if(self.verbose): 
            def earliest_and_latest(arr): return f"first {np.min(arr)%15 :5.2f}, last {np.max(arr)%15 :5.2f}" if arr else ''
            with self.cands_lock:
                sync_completed = [c.pipeline.sync.completed_time for c in self.cands_list if c.pipeline.sync.has_completed]
                demapped = [c for c in self.cands_list if c.pipeline.demap.has_completed]
                demap_completed = [c.pipeline.demap.completed_time for c in demapped if c.pipeline.demap.has_completed]
                demap_valid_ncheck = [c.pipeline.demap.completed_time for c in demapped if c.pipeline.demap.result.ncheck <= self.ncheck_max]
                decode_completed = [c.pipeline.decode.completed_time for c in self.cands_list if c.pipeline.decode.has_completed]
                deduped = [c.deduped for c in self.cands_list if c.deduped]
            self.tlog(f"[Cycle manager] sync_completed:   {len(sync_completed)} ({earliest_and_latest(sync_completed)})")
            self.tlog(f"[Cycle manager] demap_completed: {len(demap_completed)} ({earliest_and_latest(demap_completed)})")
            self.tlog(f"[Cycle manager] ncheck_valid: {len(demap_valid_ncheck)} ({earliest_and_latest(demap_valid_ncheck)})")
            self.tlog(f"[Cycle manager] decode_completed:  {len(decode_completed)} ({earliest_and_latest(decode_completed)})")
            self.tlog(f"[Cycle manager] deduped:  {len(deduped)} ({earliest_and_latest(deduped)})")            

    def manage_cycle(self):
        cycle_searched = True
        cycle_counter = 0
        cycle_time_prev = 0
        to_decode =[]
        to_demap = []
        while self.running:
            time.sleep(0.001)

            rollover = self.spectrum.cycle_time() < cycle_time_prev 
            cycle_time_prev = self.spectrum.cycle_time()

            if(rollover):
                cycle_counter +=1
                self.tlog(f"\n[Cycle manager] rollover detected at {self.spectrum.cycle_time():.2f}")
                if(cycle_counter > self.max_cycles):
                    self.running = False
                    break
                cycle_searched = False
                self.check_for_tx()
                self.spectrum.pgrid_fine_ptr = 0
                self.stats_printed = False
                with self.cands_lock:
                    self.cands_list = [c for c in self.cands_list
                                       if (c.pipeline.decode.is_in_progress and time.time() - c.pipeline.sync.started_time < 15)]
                if not self.audio_started: self.start_audio()

            if (self.spectrum.pgrid_fine_ptr > self.spectrum.h_search and not cycle_searched):
                    cycle_searched = True
                    if(self.verbose): self.tlog(f"[Cycle manager] Search spectrum ...")
                    new_cands = self.spectrum.search()
                    if(self.verbose): self.tlog(f"[Cycle manager] Spectrum searched -> {len(new_cands)} candidates")
                    if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)
                    with self.cands_lock:
                        self.cands_list = self.cands_list + new_cands

            if(self.spectrum.pgrid_fine_ptr >= self.spectrum.h_demap):
                with self.cands_lock:
                    to_demap = [c for c in self.cands_list
                                if (self.spectrum.pgrid_fine_ptr > c.pipeline.sync.result.payload_hop_idxs[-1]
                                and not c.pipeline.demap.has_started)]
                for c in to_demap[:5]:
                    c.demap(self.spectrum)
                with self.cands_lock:
                    demapped = [c for c in self.cands_list if c.pipeline.demap.has_completed]
                    to_decode =  [c for c in demapped if c.pipeline.demap.result.ncheck <= self.ncheck_max
                                and not c.pipeline.decode.has_started]
                    if(len(demapped) < len(self.cands_list)):
                       to_decode = [c for c in to_decode if c.pipeline.demap.result.ncheck <= 28]
                        
                for c in to_decode[:1]:
                    c.decode(self.process_decode)

            if(self.spectrum.cycle_time() > self.sigspec.cycle_seconds - 0.25 and not self.stats_printed):
                self.stats_printed = True
                self.print_stats()

    def process_decode(self, c, payload_bits):
        c.msg = FT8_unpack(payload_bits)
        c.payload_bits = payload_bits
        c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
        c.cyclestart_str = self.spectrum.cyclestart_str(c.pipeline.demap.started_time)
        c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
        if(not c.dedupe_key in self.duplicate_filter):
            self.duplicate_filter.add(c.dedupe_key)
            c.h0_idx = c.pipeline.sync.result.h0_idx
            c.f0_idx = c.pipeline.sync.result.f0_idx
            c.dt = c.h0_idx * self.spectrum.dt-0.7
            c.fHz = int(c.f0_idx * self.spectrum.df)
            self.onSuccessfulDecode(c)
        else:
            c.deduped = time.time()

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
            

                       




                 
