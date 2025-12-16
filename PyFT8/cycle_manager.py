import threading
import numpy as np
from .timers import *
from .audio import find_device, AudioIn
from .FT8_demodulator import FT8Demodulator
from .decode174_91_v5_5 import LDPC174_91
from .FT8_unpack import FT8_unpack
import pyaudio
import queue
import wave

class Spectrum:
    def __init__(self, demodspec):
        self.sigspec = demodspec.sigspec
        self.hops_persymb = demodspec.hops_persymb
        self.fbins_pertone = demodspec.fbins_pertone
        self.max_freq = 3500 
        self.dt = demodspec.samples_perhop / demodspec.sample_rate
        self.FFT_len = int(demodspec.fbins_pertone * demodspec.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = demodspec.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        self.df = self.max_freq / self.nFreqs
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * demodspec.hops_persymb)
        self.candidate_size = (self.sigspec.num_symbols * demodspec.hops_persymb,
                               self.sigspec.tones_persymb * demodspec.fbins_pertone)
        
        self._csync = np.full((self.sigspec.costas_len, self.candidate_size[1]), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* demodspec.fbins_pertone, (tone+1) * demodspec.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*demodspec.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * demodspec.hops_persymb

        self.fine_grid_complex = np.zeros((2 * self.hops_percycle, self.nFreqs), dtype = np.complex64)
        self.fine_grid_pointer = 0
        self.occupancy = np.zeros(self.nFreqs)


class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None, input_device_keywords = None,
                 sync_score_thresh = 3, max_ncheck = 30, max_iters = 10,  max_cycles = 5000, return_candidate = False):
        self.running = True
        self.cands_list = []
        self.return_candidate = return_candidate
        self.sigspec = sigspec
        self.max_ncheck = max_ncheck
        self.demod = FT8Demodulator(sigspec)
        self.spectrum = Spectrum(self.demod)
        self.spectrum_lock = threading.Lock()
        self.input_device_idx = find_device(input_device_keywords)
        self.audio_in = AudioIn(self, np.kaiser(self.spectrum.FFT_len, 20))
        self.ldpc = LDPC174_91(max_iters = max_iters, max_ncheck = max_ncheck)

        self.audio_in_wav = audio_in_wav
        self.max_cycles = max_cycles
        self.cycle_countdown = max_cycles
        self.cyclestart_str = None
        self.prev_cycle_time = 1e40
        n_hops_sync_band  = self.demod.slack_hops + np.max(self.spectrum.hop_idxs_Costas)
        self.t_search = n_hops_sync_band * self.spectrum.dt
        self.i_demap = 73 * self.demod.hops_persymb

        self.cands_list = []
        self.cands_lock = threading.Lock()
        self.sync_score_thresh = sync_score_thresh
        self.duplicate_filter = set()
        self.total_ldpc_time = 0

        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy

        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def manage_cycle(self):
        timedLog("[Cycle manager] waiting for end of partial cycle")
        while (tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds  - 0.1 :
            sleep(0.01)
        threading.Thread(target = self.audio_in.stream, args=(self.audio_in_wav,), daemon=True).start()
        
        while self.running:
            sleep(0.05)
            cycle_time = tnow() % self.demod.sigspec.cycle_seconds
            if (cycle_time < self.prev_cycle_time): 
                self.cycle_countdown -=1
                if not self.cycle_countdown: self.running = False
                timedLog(f"[Cycle manager] rollover detected at {cycle_time:.2f}")
                self.output_timings()
                dumped_stats = False
                cycle_searched = False
                self.spectrum.fine_grid_pointer = 0
                self.cyclestart_str = cyclestart_str()
                still_live = [c for c in self.cands_list if not c.ldpc_returned]
                with self.cands_lock:
                    self.cands_list = [c for c in still_live if tnow() - c.cycle_start < 15
                                       and not c.demap_returned]
                    timedLog(f"[Cycle manager] {len(self.cands_list)} candidates carried over")
            else:
                if (cycle_time > self.t_search and not cycle_searched):
                    cycle_searched = True
                    self.search_spectrum()
                if(self.spectrum.fine_grid_pointer > self.i_demap):
                    self.process_candidates()
                    
            self.prev_cycle_time = cycle_time

    def output_timings(self):
        def t(et,cb):
            return f"{et - cb :6.2f}" if et else None
        with self.cands_lock:
            demapped = [c for c in self.cands_list if c.demap_returned]
            latest_demap = np.max([c.demap_returned - c.cycle_start for c in demapped]) if len(demapped) else 0
            sent_for_decode = [c for c in self.cands_list if c.ldpc_requested]
            returned = [c for c in sent_for_decode if c.ldpc_returned]
            latest_decode = np.max([c.ldpc_returned - c.cycle_start for c in returned]) if len(returned) else 0
            success = [c for c in returned if len(c.payload_bits)]
            timedLog(f"[Cycle manager] {len(self.cands_list)} candidates, {len(demapped)} demapped (latest {latest_demap:5.2f})")
            timedLog(f"[Cycle manager] {len(sent_for_decode)} sent for decode, {len(returned)} returned (latest {latest_decode:5.2f})")
            timedLog(f"[Cycle manager] {len(success)} successful decodes")

    def search_spectrum(self):
        timedLog(f"[Cycle manager] Search spectrum ...")
        idx_n = self.spectrum.fine_grid_pointer
        idx_0 = idx_n - self.demod.slack_hops - self.sigspec.costas_len * self.demod.hops_persymb
        with self.spectrum_lock:
            self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[idx_0:idx_n,:].copy()
        cands = self.demod.find_syncs(self.spectrum, self.sync_score_thresh)
        with self.cands_lock:
            self.cands_list = self.cands_list + cands
        timedLog(f"[Cycle manager] Spectrum searched -> {len(self.cands_list)} candidates")
        if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

    def process_candidates(self):
        with self.cands_lock:
            to_decode = [c for c in self.cands_list if (self.spectrum.fine_grid_pointer > c.last_data_hop and not c.demap_requested)]
        for c in to_decode:
            c.demap_requested = tnow()
            with self.spectrum_lock:
                c.synced_grid_complex = self.spectrum.fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0], c.origin[1]:c.origin[1]+c.size[1]].copy()
            c.llr, c.snr = self.demod.demap_candidate(c)
            c.demap_returned = tnow()
            if (not c.ldpc_requested):
                c.ldpc_requested = tnow()
                threading.Thread(target=self.decode, args = (c,), daemon=True).start()
                    
    def decode(self, c):
        self.ldpc.decode(c)
        with self.cands_lock:
            c.ldpc_returned = tnow()
        self.total_ldpc_time +=c.ldpc_returned - c.ldpc_requested
        message_parts = FT8_unpack(c.payload_bits)
        if(message_parts):
            key = c.cyclestart_str+" "+' '.join(message_parts)
            if(not key in self.duplicate_filter):
                self.duplicate_filter.add(key)
                freq_str = f"{c.origin[3]:4.0f}"
                time_str = f"{c.origin[2]:4.1f}"
                with self.cands_lock:
                    c.decode_dict = {
                            'cyclestart_str':c.cyclestart_str, 'decoder':'PyFT8', 'freq':float(freq_str), 't_decode':tnow(), 
                            'dt':float(time_str), 't0_idx':c.origin[0],'f0_idx':c.origin[1],
                            'call_a':message_parts[0], 'call_b':message_parts[1], 'grid_rpt':message_parts[2],
                            'sync_score':c.sync_score, 'snr':c.snr, 
                            'ncheck_initial':c.ncheck_initial, 'ldpc_time':c.ldpc_returned - c.ldpc_requested
                            }
                self.onSuccessfulDecode(c if self.return_candidate else c.decode_dict)  
                       




                 
