import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum, Candidate
import pyaudio
import queue

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in = [], verbose = True,
                 max_iters = 90, max_stall = 8, max_ncheck = 30,
                 sync_score_thresh = 3, llr_sd_thresh = 2):
        self.verbose = verbose
        self.last_cycle_time = 1e40
        self.live = True
        self.sigspec = sigspec
        self.sync_score_thresh = sync_score_thresh
        self.llr_sd_thresh = llr_sd_thresh
        self.spectrum_lock = threading.Lock()
        self.cands_list_lock = threading.Lock()
        self.last_cycle_time = 1e9
        self.cyclestart_str = None
        self.demod = FT8Demodulator(sigspec, max_iters, max_stall, max_ncheck)
        self.spectrum = Spectrum(self.demod)
        self.running = True
        self.time_window = np.kaiser(self.spectrum.FFT_len, 20)
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        self.cands_list = []
        self.input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=200)
        self.n_spectrum_denied = 0
        self.n_decode_success = 0
        self.n_decode_success_cumve = 0
        self.demap_wait = 0
        self.ldpc_wait = 0
        self.n_ldpc_send = 0
        self.n_ldpc_return =0

        timers.timedLog("Waiting for first cycle start")
        while (timers.tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds -1 :
            timers.sleep(0.1)
        threading.Thread(target=self.threaded_audio_stream, daemon=True).start()
        threading.Thread(target=self.threaded_spectrum_filler, daemon=True).start()
        threading.Thread(target=self.threaded_spectrum_tasks, daemon=True).start()
        threading.Thread(target=self.threaded_demap_manager, daemon=True).start()
        threading.Thread(target=self.threaded_decode_manager, daemon=True).start()
        threading.Thread(target=self.threaded_UI_updater, daemon=True).start()

#============================================
# Audio in and FFT
#============================================
    def threaded_audio_stream(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=self.demod.sample_rate,
                         input=True, input_device_index = self.input_device_idx,
                         frames_per_buffer=self.demod.samples_perhop, stream_callback=None)
        while self.running:
            timers.sleep(0.001)
           # config.pause_ldpc = True
            data = stream.read(self.demod.samples_perhop, exception_on_overflow=False)
            self.audio_queue.put(data)
           # config.pause_ldpc = False
            
    def threaded_spectrum_filler(self):
        self.spectrum = Spectrum(self.demod)
        while self.running:
            timers.sleep(0.001)
            audio_samples = np.frombuffer(self.audio_queue.get(), dtype=np.int16)
            #with self.spectrum_lock:
            self.spectrum.audio_in.extend(audio_samples)    
            FFT_start_sample_idx = int(len(self.spectrum.audio_in) - self.spectrum.FFT_len)
            if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
               # config.pause_ldpc = True
                aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len]
                aud *= self.time_window
                #with self.spectrum_lock:
                self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
                self.spectrum.nHops_loaded +=1
              #  config.pause_ldpc = False

#============================================
# Rollover and early candidate search
#============================================
    def threaded_spectrum_tasks(self):
        while self.running:
            timers.sleep(0.1)
            
            cycle_time = timers.tnow() % self.demod.sigspec.cycle_seconds 
            if (self.live and cycle_time < self.last_cycle_time):
                self.spectrum.cycle_start_offset = cycle_time
                self.cycle_end_time = timers.tnow() + self.demod.sigspec.cycle_seconds
                self.cyclestart_str = timers.cyclestart_str()
                if(self.n_spectrum_denied > 0):
                    timers.timedLog(f"Warning, {self.n_spectrum_denied} candidates out of {len(self.cands_list)} requested spectrum after first hop overwritten (denied)")
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}")
                self.spectrum.reset(cycle_time)
                self.n_spectrum_denied = 0
                self.n_decode_success = 0
            self.last_cycle_time = cycle_time
            
            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop and not self.spectrum.searched):
                self.spectrum.searched = True
                config.pause_ldpc = True
                timers.timedLog("Search spectrum ...", logfile = 'pipeline.log')
              #  with self.spectrum_lock:
                self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[:self.spectrum.candidate_search_after_hop,:]
                self.demod.find_syncs(self.spectrum, self.sync_score_thresh, self.onFindSync)
                timers.timedLog("Spectrum searched", logfile = 'pipeline.log')
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)
                config.pause_ldpc = False

    def onFindSync(self, sync_result):
        c = Candidate(self.spectrum)
        c.sync_result = sync_result
        c.timings.update({'sync':timers.tnow()})
        with self.cands_list_lock:
            self.cands_list.append(c)

#============================================
# Candidate demap manager
#============================================
    def threaded_demap_manager(self):
        while self.running:
            timers.sleep(0.05)

            cands_to_demap = []
            #cands_synced = candidates found with sync_score > sync_score_thresh
            with self.cands_list_lock:
                cands_synced = [c for c in self.cands_list if c.sync_result]
            # cands_to_demap = subset of cands_synced which are 'full' and not yet sent for demap
            cands_to_demap = [c for c in cands_synced
                              if self.spectrum.nHops_loaded > c.sync_result['last_data_hop']
                              and not c.demap_requested]
                
            # for cands_to_demap, fill the candidate's part of the spectrum and demap
            for c in cands_to_demap:                
                c.demap_requested = True
                c.timings.update({'t_requested_demap':timers.tnow()})
                origin = c.sync_result['origin']
                if(c.cyclestart_str != self.cyclestart_str):
                    if (self.spectrum.nHops_loaded > c.sync_result['first_data_hop']):
                        self.n_spectrum_denied +=1
                        c.demap_result = {'llr_sd':0,'llr':None,'snr':None}
                    continue
                with self.spectrum_lock:
                    c.synced_grid_complex = self.spectrum.fine_grid_complex[origin[0]:origin[0]+c.size[0],
                                                                            origin[1]:origin[1]+c.size[1]].copy()
                c.timings.update({'fill':timers.tnow()})
                #config.pause_ldpc = True
                self.demod.demap_candidate(self.spectrum, c)
                #config.pause_ldpc = False
                c.timings.update({'t_end_demap':timers.tnow()})
                self.demap_wait += c.timings['t_end_demap'] - c.timings['t_requested_demap']

#============================================
# Candidate decode manager
#============================================
    def threaded_decode_manager(self):
        while self.running:
            timers.sleep(0.05)
            
            # demapped = all candidates that have been demapped
            with self.cands_list_lock:
                demapped = [c for c in self.cands_list if c.demap_result]

            # for demapped candidates with llr_sd below llr_sd_thesh, remove from global list self.cands_list
            # for the others, build a list to send to ldpc
            demapped_success = []
            with self.cands_list_lock:
                for c in demapped:
                    if (c.demap_result['llr_sd'] < self.llr_sd_thresh):
                        self.cands_list.remove(c)
                    else:
                        demapped_success.append(c)
                
            # cands_for_ldpc = cands in demapped_success that have not already been sent for ldpc
            cands_for_ldpc = [c for c in demapped_success if not c.ldpc_requested]
            cands_for_ldpc.sort(key=lambda c: -c.demap_result['llr_sd'])
            for c in cands_for_ldpc:
                if(self.n_ldpc_send - self.n_ldpc_return < 500):
                    c.ldpc_requested = True
                    c.timings.update({'t_requested_ldpc':timers.tnow()})
                    self.n_ldpc_send +=1
                    threading.Thread(target=self.demod.decode_candidate, kwargs={'candidate':c, 'onDecode':self.onDecode}, daemon=True).start()
            
    def onDecode(self, c):
        with self.cands_list_lock:
            self.cands_list.remove(c)
            
        c.timings.update({'t_end_ldpc':timers.tnow()})
        self.ldpc_wait += c.timings['t_end_ldpc'] - c.timings['t_requested_ldpc']
        self.n_ldpc_return +=1
        if(c.decode_success):
            self.n_decode_success +=1
            self.n_decode_success_cumve +=1
            origin = c.sync_result['origin']
            dt = origin[2] - 0.8 
            if(dt > self.sigspec.cycle_seconds//2): dt -=self.sigspec.cycle_seconds
            dt = f"{dt:4.1f}"
            c.decode_result.update({'dt': dt})
            key = c.message
            if(not key in self.spectrum.duplicate_filter):
                self.spectrum.duplicate_filter.add(key)
                self.onSuccessfulDecode(c)
                
        if(self.verbose):
            timers.timedLogCSV(c.metrics, 'success_fail_metrics.csv')

#============================================
# UI counters update
#============================================
    def threaded_UI_updater(self):
        while self.running:
            timers.sleep(0.25)
            
            loading_info = {'n_candidates': len(self.cands_list),
                            'in_ldpc': self.n_ldpc_send,
                            'ldpc_results': self.n_ldpc_return,
                            'n_decode_success':  self.n_decode_success_cumve}
            timers.timedLog(loading_info, logfile = 'pipeline.log',silent = True)
            send_to_ui_ws("decode_queue", loading_info)
            graphic_bars = { "n_synced":   len(self.cands_list),
                             "demap_wait": self.demap_wait,
                             "ldpc_wait":  self.ldpc_wait,
                             "n_decode_success":  self.n_decode_success}
            send_to_ui_ws("graphic_bars", graphic_bars)
            
            

 
