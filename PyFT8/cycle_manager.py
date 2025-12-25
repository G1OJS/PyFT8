import threading
from types import SimpleNamespace
import numpy as np
import time
from .audio import find_device, AudioIn
from .decode174_91_v6_0 import LDPC174_91
from .FT8_unpack import FT8_unpack
import pyaudio
import queue
import wave
import os
eps = 1e-12

ldpc = LDPC174_91()

def safe_pc(x,y):
    return 100*x/y if y>0 else 0

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
        self.ldpc = StageProps()
        self.osd = StageProps()
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
        llr0 = np.log(np.max(pgrid[:, [4,5,6,7]], axis=1)) - np.log(np.max(pgrid[:, [0,1,2,3]], axis=1))
        llr1 = np.log(np.max(pgrid[:, [2,3,4,7]], axis=1)) - np.log(np.max(pgrid[:, [0,1,5,6]], axis=1))
        llr = np.log(np.max(pgrid[:, [1,2,6,7]], axis=1)) - np.log(np.max(pgrid[:, [0,3,4,5]], axis=1))
        llr = np.column_stack((llr0, llr1, llr)).ravel()
        llr_sd = np.std(llr)
        llr = 3.8 * llr / llr_sd
        self.pipeline.demap.complete(success=True, result=llr, metrics=SimpleNamespace(pmax=np.max(pgrid),llr_sd=llr_sd))

    def ldpc(self, max_iters, max_ncheck):
        self.pipeline.ldpc.start()
        llr = self.pipeline.demap.result
        ldpc_res = ldpc.decode(llr, max_iters, max_ncheck)
        payload_bits = ldpc_res[0] if ldpc_res else None
        self.pipeline.ldpc.complete(
            success = bool(payload_bits),
            result = SimpleNamespace(
                payload_bits = payload_bits,
                llr_from_ldpc = ldpc_res[3] if ldpc_res else None
            ),
            metrics = SimpleNamespace(
                ncheck_initial = ldpc_res[1] if ldpc_res else None,
                n_its = ldpc_res[2] if ldpc_res else None
            )
        )

    def osd(self, max_iters, max_ncheck):
        self.pipeline.osd.start()
        llr = self.pipeline.ldpc.result.llr_from_ldpc
        K = 20   # magic %
        abs_llr = np.abs(llr)
        thresh = np.percentile(abs_llr, K)
        freeze = abs_llr >= thresh
        BIG = 40.0   # magic
        iflip = -1
        N = 0
        for iflip, f in enumerate(freeze):
            if(not f):
                N +=1
                tmp = llr[iflip] 
                llr[iflip] = -BIG*np.sign(llr[iflip])
                ldpc_res = ldpc.decode(llr, max_iters, max_ncheck)
                payload_bits = ldpc_res[0] if ldpc_res else None
                if(payload_bits): break
                llr[iflip] = tmp
            
        payload_bits = ldpc_res[0] if ldpc_res else None
        self.pipeline.osd.complete(
            success = bool(payload_bits),
            result = SimpleNamespace(payload_bits = payload_bits),
            metrics = SimpleNamespace(
                ncheck_initial = ldpc_res[1] if ldpc_res else None,
                n_its = ldpc_res[2] if ldpc_res else None,
                N = N
            )
        )

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

    def search(self, sync_score_thresh):
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
            if(best[2] > sync_score_thresh):
                c = Candidate()
                c.record_sync(self, *best)
                cands.append(c)
        return cands

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 sync_score_thresh = 3, max_ncheck = 30, max_iters = 10,  max_cycles = 5000, 
                 input_device_keywords = None, output_device_keywords = None, verbose = False):
        self.running = True
        self.verbose = verbose
        self.max_ncheck = max_ncheck
        self.max_iters = max_iters
        self.audio_in_wav = audio_in_wav
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.max_cycles = max_cycles
        self.cands_list = []
        self.cands_lock = threading.Lock()
        self.sync_score_thresh = sync_score_thresh
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
                demap_completed = [c.pipeline.demap.completed_time for c in self.cands_list if c.pipeline.demap.has_completed]
                ldpc_completed = [c.pipeline.ldpc.completed_time for c in self.cands_list if c.pipeline.ldpc.has_completed]
                osd_completed = [c.pipeline.osd.completed_time for c in self.cands_list if c.pipeline.osd.has_completed]
                osd_succeeded = [c.pipeline.osd.completed_time for c in self.cands_list if c.pipeline.osd.success]
                deduped = [c.deduped for c in self.cands_list if c.deduped]
            self.tlog(f"[Cycle manager] sync_completed:   {len(sync_completed)} ({earliest_and_latest(sync_completed)})")
            self.tlog(f"[Cycle manager] demap_completed: {len(demap_completed)} ({earliest_and_latest(demap_completed)})")
            self.tlog(f"[Cycle manager] ldpc_completed:  {len(ldpc_completed)} ({earliest_and_latest(ldpc_completed)})")
            self.tlog(f"[Cycle manager] osd_completed:  {len(osd_completed)} ({earliest_and_latest(osd_completed)})")
            self.tlog(f"[Cycle manager] osd_succeeded:  {len(osd_succeeded)} ({earliest_and_latest(osd_succeeded)})")
            self.tlog(f"[Cycle manager] deduped:  {len(deduped)} ({earliest_and_latest(deduped)})")            
            self.tlog(f"[Cycle manager] osd success rate:  {safe_pc(len(osd_succeeded),len(osd_completed)):5.0f}")


    def manage_cycle(self):
        cycle_searched = True
        cycle_counter = 0
        cycle_time_prev = 0
        to_ldpc =[]
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
                                       if (c.pipeline.ldpc.is_in_progress and time.time() - c.pipeline.sync.started_time < 15)]
                if not self.audio_started: self.start_audio()

            if (self.spectrum.pgrid_fine_ptr > self.spectrum.h_search and not cycle_searched):
                    cycle_searched = True
                    if(self.verbose): self.tlog(f"[Cycle manager] Search spectrum ...")
                    new_cands = self.spectrum.search(self.sync_score_thresh)
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
                    to_ldpc = [c for c in self.cands_list if c.pipeline.demap.has_completed and not c.pipeline.ldpc.has_started]
                for c in to_ldpc[:1]:
                    c.ldpc(self.max_iters, self.max_ncheck)
                    if(c.pipeline.ldpc.success):
                        self.process_decode(c, c.pipeline.ldpc.result.payload_bits)

            if(self.spectrum.cycle_time() > self.sigspec.cycle_seconds - 3.5
               and self.spectrum.cycle_time() < self.sigspec.cycle_seconds - 0.5):
                if not len(to_ldpc) and not len(to_demap):
                    with self.cands_lock:
                        to_osd = [c for c in self.cands_list if c.pipeline.ldpc.has_completed and not c.pipeline.ldpc.success and not c.pipeline.osd.has_started]
                    to_osd.sort(key = lambda c: c.pipeline.ldpc.metrics.ncheck_initial)
                    for c in to_osd[:1]:
                        c.osd(self.max_iters, self.max_ncheck+5)
                        if(c.pipeline.osd.success):
                            self.process_decode(c, c.pipeline.osd.result.payload_bits)

            if(self.spectrum.cycle_time() > self.sigspec.cycle_seconds - 0.25 and not self.stats_printed):
                self.stats_printed = True
                self.print_stats()

    def process_decode(self, c, payload_bits):
        c.msg = FT8_unpack(payload_bits)
        c.payload_bits = payload_bits
        c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
        c.cyclestart_str = self.spectrum.cyclestart_str(c.pipeline.demap.started_time)
        c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)+str(c.pipeline.osd.success)
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
            

                       




                 
