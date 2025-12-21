import threading
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

class Candidate:
    next_id = 0
    def __init__(self, best, spectrum):
        self.id = Candidate.next_id
        Candidate.next_id +=1
        self.spectrum = spectrum
        self.sigspec = spectrum.sigspec
        self.demap_requested = False
        self.demap_returned = False
        self.ldpc_requested = False
        self.ldpc_returned = False
        self.ncheck_initial = 5000
        self.cyclestart_str = None
        self.sync_score = best[2]
        self.sync_returned = time.time()
        self.origin = (best[0], best[1], self.spectrum.dt * best[0], self.spectrum.df * (best[1] + 1))
        self.last_payload_symbol = self.sigspec.payload_symb_idxs[-1]
        self.last_hop = best[0] + self.sigspec.num_symbols * spectrum.hops_persymb
        self.last_data_hop = best[0] + (self.last_payload_symbol+1) * spectrum.hops_persymb
        self.sync_returned = time.time()

    def set_decode_params(self, max_iters = 15, max_ncheck = 30):
        self.max_iters = max_iters
        self.max_ncheck = max_ncheck

    def demap(self):
        self.demap_requested = time.time()
        hop_idxs = [self.origin[0] + s * self.spectrum.hops_persymb for s in self.sigspec.payload_symb_idxs] 
        f_idxs =   [self.origin[1] + self.spectrum.fbins_pertone //2 + self.spectrum.fbins_pertone * t for t in range(self.sigspec.tones_persymb)]
        pgf = self.spectrum.pgrid_fine
        self.pgrid_fine = pgf[hop_idxs[0]:hop_idxs[-1], f_idxs[0]:f_idxs[-1]]
        self.pgrid = pgf[hop_idxs,:][:, f_idxs]
        pmax = np.max(self.pgrid)
        self.snr = 10*np.log10(pmax)-107
        self.snr = int(np.clip(self.snr, -24,24).item())
        self.pgrid /= pmax
        llr0 = np.log(np.max(self.pgrid[:,[4,5,6,7]], axis=1)) - np.log(np.max(self.pgrid[:,[0,1,2,3]], axis=1))
        llr1 = np.log(np.max(self.pgrid[:,[2,3,4,7]], axis=1)) - np.log(np.max(self.pgrid[:,[0,1,5,6]], axis=1))
        llr2 = np.log(np.max(self.pgrid[:,[1,2,6,7]], axis=1)) - np.log(np.max(self.pgrid[:,[0,3,4,5]], axis=1))
        llr = np.column_stack((llr0, llr1, llr2)).ravel()
        self.llr = 3.8*llr/np.std(llr)
        self.demap_returned = time.time()

    def decode(self):
        self.ldpc_requested = time.time()
        ldpc.decode(self)
        self.ldpc_returned = time.time()
        self.message_parts = FT8_unpack(self.payload_bits)
        cyclestart_time = self.sigspec.cycle_seconds * int(self.demap_requested / self.sigspec.cycle_seconds)
        self.cyclestart_str = time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))
        self.dedupe_key = self.cyclestart_str+" "+' '.join(self.message_parts) if(self.message_parts) else None


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
        self.df = self.max_freq / self.nFreqs
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * self.hops_persymb)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone

        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self._csync = np.full((self.sigspec.costas_len, self.fbins_per_signal), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*self.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb

        self.fine_grid_complex = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.complex64)
        self.fine_grid_pointer = 0
        self.cycle_searched = True

        self.max_start_hop = int(1.9 / self.dt)
        self.h_search = self.max_start_hop + self.nhops_costas 
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.lock = threading.Lock()

    @property
    def pgrid_fine(self):
        with self.lock:
            p = np.abs(self.fine_grid_complex)**2 
        return p
        
    def search(self, sync_score_thresh):
        self.cycle_searched = True
        cands = []
        f0_idxs = range(self.nFreqs - self.fbins_per_signal)
        pgrid = self.pgrid_fine[:self.h_search,:].copy()
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            p /= max_pwr
            best = (0, f0_idx, -1e30)
            for t0_idx in range(self.h_search - self.nhops_costas):
                test = (t0_idx, f0_idx, float(np.dot(p[t0_idx + self.hop_idxs_Costas ,  :].ravel(), self._csync.ravel())))
                print(p[t0_idx + self.hop_idxs_Costas ,  :].ravel())
                print(self._csync.ravel())
                print(test)
                stop
                if test[2] > best[2]:
                    best = test
            if(best[2] > sync_score_thresh):
                c = Candidate(best, self)
                cands.append(c)
        return cands
                
                    
class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 sync_score_thresh = 3, max_ncheck = 30, max_iters = 10,  max_cycles = 5000, return_candidate = False,
                 input_device_keywords = None, output_device_keywords = None, verbose = False, concise = False):
        self.running = True
        self.verbose = verbose
        self.concise = concise
        self.return_candidate = return_candidate
        
        self.spectrum = Spectrum(sigspec)
        self.cycle_seconds = self.spectrum.sigspec.cycle_seconds
        self.max_ncheck = max_ncheck
        self.max_iters = max_iters
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.audio_in = AudioIn(self, np.kaiser(self.spectrum.FFT_len, 20))
        self.audio_in_wav = audio_in_wav
        self.max_cycles = max_cycles
        self.cycle_countdown = max_cycles
        self.cyclestart_str = None
        self.prev_cycle_time = -1e40
        self.cands_list = []
        self.cands_lock = threading.Lock()
        self.sync_score_thresh = sync_score_thresh
        self.duplicate_filter = set()
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        if(self.output_device_idx):
            from .audio import AudioOut
            self.audio_out = AudioOut
            
        threading.Thread(target = self.audio_in.stream, args=(self.audio_in_wav,), daemon=True).start()
        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def manage_cycle(self):
        while self.running:
            time.sleep(0)
            self.cycle_time = time.time() % self.spectrum.sigspec.cycle_seconds
            rollover = (self.cycle_time < self.prev_cycle_time)
            self.prev_cycle_time = self.cycle_time

            if(rollover):
                if not self.cycle_countdown:
                    self.running = False
                    break
                self.check_for_tx()
                self.cycle_countdown -=1
                self.spectrum.cycle_searched = False
                self.spectrum.fine_grid_pointer = 0
                self.cyclestart_str = time.strftime("%y%m%d_%H%M%S", time.gmtime(self.cycle_seconds * int(time.time() / self.cycle_seconds)))
                if(self.verbose):
                    def latest(arr): return f"{np.max(arr)%15 :5.2f}" if arr else ''
                    with self.cands_lock:
                        synced = [c.sync_returned for c in self.cands_list if c.sync_score]
                        demapped = [c.demap_returned for c in self.cands_list if c.demap_returned]
                        decoded = [c.ldpc_returned for c in self.cands_list if c.ldpc_returned]
                    print(f"[Cycle manager] synced:   {len(synced)} (latest at {latest(synced)})")
                    print(f"[Cycle manager] demapped: {len(demapped)} (latest at {latest(demapped)})")
                    print(f"[Cycle manager] decoded:  {len(decoded)} (latest at {latest(decoded)})")
                    print(f"\n[Cycle manager] rollover detected at {self.cycle_time:.2f}")
                with self.cands_lock:
                    self.cands_list = [c for c in self.cands_list
                                       if (not c.ldpc_returned and time.time() - c.sync_returned < 15)]
            else:
                if (self.spectrum.fine_grid_pointer >= self.spectrum.h_search and not self.spectrum.cycle_searched):
                    if(self.verbose): print(f"[Cycle manager] Search spectrum ...")
                    new_cands = self.spectrum.search(1e-22)
                    if(self.verbose): print(f"[Cycle manager] Spectrum searched -> {len(new_cands)} candidates")
                    if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)
                    with self.cands_lock:
                        self.cands_list = self.cands_list + new_cands
                if(self.spectrum.fine_grid_pointer >= self.spectrum.h_demap):
                    with self.cands_lock:
                        to_demap = [c for c in self.cands_list if (self.spectrum.fine_grid_pointer > c.last_data_hop and not c.demap_requested)]
                    for c in to_demap[:5]:
                        c.demap()
                    with self.cands_lock:
                        to_decode = [c for c in self.cands_list if c.demap_returned and not c.ldpc_requested]
                    for c in to_decode[:1]:
                        c.set_decode_params(self.max_iters, self.max_ncheck)
                        c.decode()
                        if(c.dedupe_key and not c.dedupe_key in self.duplicate_filter):
                            self.duplicate_filter.add(c.dedupe_key)
                            f0_str = f"{c.origin[3]:4.0f}"
                            t0_str = f"{c.origin[2]-0.7:6.3f}"
                            with self.cands_lock:
                                c.decode_dict = {
                                        'cyclestart_str':c.cyclestart_str, 'freq':int(f0_str), 'dt':float(t0_str),
                                        'call_a':c.message_parts[0], 'call_b':c.message_parts[1], 'grid_rpt':c.message_parts[2],
                                        'snr':c.snr,
                                }
                                if(not self.concise):
                                    c.decode_dict.update({
                                        't0_idx':c.origin[0],
                                        'decoder':'PyFT8', 't_decode':time.time(), 'f0_idx':c.origin[1],
                                        'sync_score':c.sync_score,  'dedupe_key':c.dedupe_key,
                                        'ncheck_initial':c.ncheck_initial, 'n_its': c.n_its
                                        })
                            self.onSuccessfulDecode(c if self.return_candidate else c.decode_dict)


    def check_for_tx(self):
        from .FT8_encoder import pack_message
        tx_msg_file = 'PyFT8_tx_msg.txt'
        if os.path.exists(tx_msg_file):
            if(not self.output_device_idx):
                print("[Tx] Tx message file found but no output device specified")
                return
            with open(tx_msg_file, 'r') as f:
                tx_msg = f.readline().strip()
                tx_freq = f.readline().strip()
            tx_freq = int(tx_freq) if tx_freq else 1000    
            print(f"[TX] transmitting {tx_msg} on {tx_freq} Hz")
            os.remove(tx_msg_file)
            c1, c2, grid_rpt = tx_msg.split()
            symbols = pack_message(c1, c2, grid_rpt)
            audio_data = self.audio_out.create_ft8_wave(self, symbols, f_base = tx_freq)
            self.audio_out.play_data_to_soundcard(self, audio_data, self.output_device_idx)
            print("[Tx] done transmitting")
            

                       




                 
