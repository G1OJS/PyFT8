import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum, Candidate
import pyaudio
import queue
import wave

class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None,
                 max_iters = 90, max_stall = 8, max_ncheck = 30,
                 sync_score_thresh = 3, max_cycles = 1e40):
        self.wav_file_start_time = None
        self.prev_cycle_time = 1e40
        self.cycle_countdown = max_cycles
        self.cyclestart_str = None
        self.sigspec = sigspec
        self.sync_score_thresh = sync_score_thresh
        self.spectrum_lock = threading.Lock()
        self.cands_list_lock = threading.Lock()
        self.demod = FT8Demodulator(sigspec, max_iters, max_stall, max_ncheck)
        self.spectrum = Spectrum(self.demod)
        self.running = True
        self.time_window = np.kaiser(self.spectrum.FFT_len, 20)
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        self.cands_list = []
        self.input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=200)
        self.n_cands_synced = 0
        self.spectrum_denied = set()
        self.n_decode_success = 0
        self.demap_wait = 0
        self.ldpc_wait = 0
        self.n_ldpc_load = 0
        self.n_total_iterations = 0
        self.duplicate_filter = set()

        threading.Thread(target=self.threaded_spectrum_filler, daemon=True).start()
        threading.Thread(target=self.threaded_spectrum_tasks, daemon=True).start()
        threading.Thread(target=self.threaded_decode_manager, daemon=True).start()
        threading.Thread(target=self.threaded_UI_updater, daemon=True).start()
        
        if(audio_in_wav):
            threading.Thread(target=self.threaded_audio_from_wav, args=(audio_in_wav,), daemon=True).start()
        else:
            threading.Thread(target=self.threaded_audio_stream, daemon=True).start()

#============================================
# Audio input
#============================================
        
    def threaded_audio_from_wav(self, wav_file):
        wf = wave.open(wav_file, 'rb')
        hop = self.demod.samples_perhop
        hop_time = self.demod.samples_perhop / self.demod.sample_rate
        while (not self.cyclestart_str):
            timers.sleep(0.01)
        self.wav_file_start_time = timers.tnow()
        timers.sleep(0.01)
        timers.timedLog(f"Playing wav file {wav_file}")
        while self.running:
            frames = wf.readframes(hop)
            if not frames:
                break
            nextHop_time = timers.tnow() + hop_time
            self.audio_queue.put(frames)
            while timers.tnow() < nextHop_time:
                timers.sleep(0.001)

    def threaded_audio_stream(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=self.demod.sample_rate,
                         input=True, input_device_index = self.input_device_idx,
                         frames_per_buffer=self.demod.samples_perhop, stream_callback=None)
        while self.running:
            timers.sleep(0.001)
            data = stream.read(self.demod.samples_perhop, exception_on_overflow=False)
            self.audio_queue.put(data)

#============================================
# 'Spectrum-filler' (FFT the audio as it arrives)
#============================================

    def threaded_spectrum_filler(self):
        self.spectrum = Spectrum(self.demod)
        while self.running:
            timers.sleep(0.001)
            audio_samples = np.frombuffer(self.audio_queue.get(), dtype=np.int16)
            with self.spectrum_lock:
                self.spectrum.audio_in.extend(audio_samples)    
            FFT_start_sample_idx = int(len(self.spectrum.audio_in) - self.spectrum.FFT_len)
            if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
                aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len]
                aud *= self.time_window
                with self.spectrum_lock:
                    self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
                    self.spectrum.nHops_loaded +=1

#============================================
# Rollover and early candidate search
#============================================
    def last_cycle_summary(self):
        cycle_time = timers.tnow() % self.demod.sigspec.cycle_seconds 
        n_cands_remaining = len(self.cands_list)
        n_demapped = len([c for c in self.cands_list if c.demap_result])
        min_ncheck_res = np.min([c.ncheck_initial for c in self.cands_list]) if n_cands_remaining else 5000
        timers.timedLog(f"   Unprocessed candidates: {n_cands_remaining}/{self.n_cands_synced} (demapped {n_demapped} with min_ncheck {min_ncheck_res})", logfile = 'pipeline.log')
        timers.timedLog(f"   Total ldpc iterations : {self.n_total_iterations}", logfile = 'pipeline.log')
        self.n_total_iterations = 0
                
    def threaded_spectrum_tasks(self):
        
        timers.timedLog("Rollover manager waiting for end of partial cycle")
        while (timers.tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds  - 0.1 :
            timers.sleep(0.01)
        while self.running:
            timers.sleep(0.1)
            cycle_time = timers.tnow() % self.demod.sigspec.cycle_seconds 
            if (cycle_time < self.prev_cycle_time): 
                if not self.cycle_countdown:
                    self.running = False
                    break
                print()
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}", logfile = 'pipeline.log')
                self.cycle_countdown -=1
                config.pause_ldpc = False
                self.cyclestart_str = timers.cyclestart_str()
                self.spectrum.reset()
                self.spectrum_denied = set()
                self.n_decode_success = 0
            self.prev_cycle_time = cycle_time
            
            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop and not self.spectrum.searched):
                self.spectrum.searched = True
                self.last_cycle_summary()
                timers.timedLog(f"Search spectrum ...", logfile = 'pipeline.log')
                with self.spectrum_lock:
                    self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[:self.spectrum.candidate_search_after_hop,:].copy()
                cands = self.demod.find_syncs(self.spectrum, self.sync_score_thresh)
                with self.cands_list_lock:
                    self.cands_list = cands
                    self.n_cands_synced = len(self.cands_list)
                timers.timedLog(f"Spectrum searched: {self.n_cands_synced} candidates", logfile = 'pipeline.log')
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

#============================================
# Decoding manager
#============================================

    def threaded_decode_manager(self):
        while self.running:
            timers.sleep(0.01)

            # cands_to_demap = subset of cands synced which can be filled and not yet sent for demap
            cands_to_demap = []
            with self.cands_list_lock:
                cands_to_demap = [c for c in self.cands_list if self.spectrum.nHops_loaded > c.sync_result['last_data_hop']
                              and not c.demap_requested]
                
            too_late = ([c for c in cands_to_demap if c.cyclestart_str != self.cyclestart_str
                              and self.spectrum.nHops_loaded > c.sync_result['first_data_hop']])
            
            for c in too_late:
                with self.cands_list_lock:
                    self.cands_list.remove(c)
                cands_to_demap.remove(c)
                self.spectrum_denied.add(c)
                   
            # fill candidate's spectrum and demap
            for c in cands_to_demap:                
                c.demap_requested = True
                c.timings.update({'t_requested_demap':timers.tnow()})
                origin = c.sync_result['origin']
                with self.spectrum_lock:
                    c.synced_grid_complex = self.spectrum.fine_grid_complex[origin[0]:origin[0]+c.size[0],
                                                                            origin[1]:origin[1]+c.size[1]].copy()
                c.timings.update({'fill':timers.tnow()})
                self.demod.demap_candidate(c)
                c.timings.update({'t_end_demap':timers.tnow()})
                self.demap_wait += c.timings['t_end_demap'] - c.timings['t_requested_demap']
                c.ncheck_initial = self.demod.ldpc.fast_ncheck(c.demap_result['llr']) #note - doesn't need all 174 bits so could be done earlier

            # cands_for_ldpc = all candidates that have been demapped and not already been sent for ldpc
            with self.cands_list_lock:
                cands_for_ldpc = [c for c in self.cands_list if c.demap_result
                                  and not c.ldpc_requested and c.cyclestart_str == self.cyclestart_str]
            
            # sort based on ncheck_initial and send for ldpc
            cands_for_ldpc.sort(key=lambda c: c.ncheck_initial) 
            for c in cands_for_ldpc:
                if(self.n_ldpc_load < 15):
                    with self.cands_list_lock:
                        self.cands_list.remove(c)
                    c.ldpc_requested = True
                    c.timings.update({'t_requested_ldpc':timers.tnow()})
                    self.n_ldpc_load +=1
                    threading.Thread(target=self.demod.decode_candidate, kwargs={'candidate':c, 'onDecode':self.onDecode}, daemon=True).start()
            
    def onDecode(self, c):

            
        c.timings.update({'t_end_ldpc':timers.tnow()})
        self.ldpc_wait += c.timings['t_end_ldpc'] - c.timings['t_requested_ldpc']
        self.n_ldpc_load -=1
        self.n_total_iterations += c.ldpc_result['n_its']
        if(c.decode_success):
            self.n_decode_success +=1
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
            
            loading_info = {'n_candidates': len(self.cands_list),
                            'n_ldpc_load': self.n_ldpc_load}
            send_to_ui_ws("decode_queue", loading_info)
            graphic_bars = { "n_synced":   len(self.cands_list),
                             "demap_wait": self.demap_wait,
                             "ldpc_wait":  self.ldpc_wait,
                             "n_decode_success":  self.n_decode_success}
            send_to_ui_ws("graphic_bars", graphic_bars)
            
            

 
