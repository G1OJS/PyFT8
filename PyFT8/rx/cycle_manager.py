import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator
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
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 max_iters = 90, max_stall = 8, max_ncheck = 30,
                 sync_score_thresh = 3, max_cycles = 1e40):
        self.running = True
        self.sigspec = sigspec
        self.max_ncheck = max_ncheck
        self.demod = FT8Demodulator(sigspec, max_iters, max_stall, max_ncheck)
        self.spectrum = Spectrum(self.demod)
        self.spectrum_lock = threading.Lock()
        self.audio_in = audio.AudioIn(self, np.kaiser(self.spectrum.FFT_len, 20))

        self.audio_in_wav = audio_in_wav
        self.cycle_countdown = max_cycles
        self.cyclestart_str = None
        self.prev_cycle_time = 1e40
        n_hops_sync_band  = self.demod.slack_hops + np.max(self.spectrum.hop_idxs_Costas)
        self.t_search = n_hops_sync_band * self.spectrum.dt

        config.cands_list = []
        self.cands_list_lock = threading.Lock()
        self.sync_score_thresh = sync_score_thresh
        self.n_decode_success = 0
        self.duplicate_filter = set()
        self.n_in_ldpc = 0

        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy

        threading.Thread(target=self.threaded_spectrum_tasks, daemon=True).start()
        threading.Thread(target=self.threaded_demap_manager, daemon=True).start()
        threading.Thread(target=self.threaded_decode_manager, daemon=True).start()
        threading.Thread(target=self.threaded_UI_updater, daemon=True).start()

#============================================
# Rollover and early candidate search
#============================================
    def threaded_spectrum_tasks(self):
        timers.timedLog("Rollover manager waiting for end of partial cycle")
        while (timers.tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds  - 0.1 :
            timers.sleep(0.01)
        threading.Thread(target = self.audio_in.stream, args=(self.audio_in_wav,), daemon=True).start()
        cycle_searched = False
        while self.running:
            timers.sleep(0.25)
            cycle_time = timers.tnow() % self.demod.sigspec.cycle_seconds 
            if (cycle_time < self.prev_cycle_time): 
                if not self.cycle_countdown:
                    self.running = False
                    break
                self.spectrum.fine_grid_pointer = 0
                print()
                
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}", logfile = 'pipeline.log')
                self.cycle_countdown -=1
                self.cyclestart_str = timers.cyclestart_str()
                self.n_decode_success = 0
                cycle_searched = False
            self.prev_cycle_time = cycle_time
            
            if (cycle_time > self.t_search and not cycle_searched):
                cycle_searched = True

                with self.cands_list_lock:
                    config.cands_list = []
                timers.timedLog(f"Search spectrum ...", logfile = 'pipeline.log')
                idx_n = self.spectrum.fine_grid_pointer
                idx_0 = idx_n - self.demod.slack_hops - self.sigspec.costas_len * self.demod.hops_persymb
                
                with self.spectrum_lock:
                    self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[idx_0:idx_n,:].copy()
                cands = self.demod.find_syncs(self.spectrum, self.sync_score_thresh)
                with self.cands_list_lock:
                    config.cands_list = cands

                timers.timedLog(f"Spectrum searched -> {len(config.cands_list)} candidates", logfile = 'pipeline.log')
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

#============================================
# Decoding manager
#============================================

    def threaded_demap_manager(self):
        # find candidates that can have spectrum filled, fill and demap
        while self.running:
            timers.sleep(0.01)

            with self.cands_list_lock:
                tmp_list = [c for c in config.cands_list if (
                                  self.spectrum.fine_grid_pointer > c.sync_result['last_data_hop']
                              or (self.cyclestart_str != c.cyclestart_str and self.spectrum.fine_grid_pointer +  self.spectrum.hops_percycle > c.sync_result['last_data_hop'])
                                  )]

            for c in tmp_list:                
                if(not c.demap_requested):
                    c.demap_requested = timers.tnow()
                    origin = c.sync_result['origin']
                    with self.spectrum_lock:
                        c.synced_grid_complex = self.spectrum.fine_grid_complex[origin[0]:origin[0]+c.size[0],
                                                                                origin[1]:origin[1]+c.size[1]].copy()
                self.demod.demap_candidate(c)
                c.ncheck_initial = self.demod.ldpc.fast_ncheck(c.demap_result['llr'])

    def threaded_decode_manager(self):
        # send all candidates that have been demapped to ldpc
        while self.running:
            timers.sleep(0.01)
            if(self.n_in_ldpc >25): #magic number
                continue

            with self.cands_list_lock:
                tmp_list = [c for c in config.cands_list if c.demap_result]

            tmp_list.sort(key = lambda c: c.ncheck_initial)
            for c in tmp_list:
                if(not c.ldpc_requested):
                    c.ldpc_requested = timers.tnow()
                    self.n_in_ldpc +=1
                    threading.Thread(target=self.demod.decode_candidate, kwargs={'candidate':c, 'onDecode':self.onDecode}, daemon=True).start()
                    
    def onDecode(self, c):
        self.n_in_ldpc -=1
        if(c.decode_success):
            origin = c.sync_result['origin']
            dt = origin[2] - 0.8 
            if(dt > self.sigspec.cycle_seconds//2): dt -=self.sigspec.cycle_seconds
            dt = f"{dt:4.1f}"
            c.decode_result.update({'dt': dt})
            key = c.cyclestart_str+" "+c.message
            if(not key in self.duplicate_filter):
                self.duplicate_filter.add(key)
                if(self.onSuccessfulDecode):
                    self.onSuccessfulDecode(c)


#============================================
# UI counters update
#============================================
    def threaded_UI_updater(self):
        while self.running:
            timers.sleep(0.25)
            
            loading_metrics = { "n_synced":   len(config.cands_list),
                             "n_demapped": len([c for c in config.cands_list if c.demap_result]),
                             "n_in_ldpc": self.n_in_ldpc,
                             "n_decoded": len([c for c in config.cands_list if c.ldpc_result]),
                             "n_decode_success":  len([c for c in config.cands_list if c.decode_success])}
            send_to_ui_ws("loading_metrics", loading_metrics)
            
            


