import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum
import pyaudio
import queue

class Cycle_manager():
    def __init__(self, onDecode, onOccupancy,
                 prioritise_rxfreq = False, audio_in = [], verbose = True,
                 sync_score_thresh = 3, max_iters = 90, max_stall = 8,
                 max_ncheck = 40, min_sd = 2):
        self.verbose = verbose
        self.cand_lock = threading.Lock()
        self.max_lifetime = 10
        self.last_cycle_time = 16
        self.sync_score_thresh = sync_score_thresh
        self.demod = FT8Demodulator(max_iters, max_stall, max_ncheck, min_sd)
        self.running = True
        self.spectrum = Spectrum(self.demod)
        self.spectrum.nHops_loaded = 0
        self.decode_load = 0
        self.time_window = np.kaiser(self.spectrum.FFT_len, 20)
        self.onDecode = onDecode
        self.onOccupancy = onOccupancy
        self.cands_to_decode = []
        self.prioritise_Hz = config.rxfreq if prioritise_rxfreq else False
        self.input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=50)
        # audio_in is e.g. from wav file for testing, otherwise start monitoring sound card
        if(any(audio_in)):
            self.find_candidates_from_audio_in(audio_in, self.sync_score_thresh)
        else:
            while int(timers.tnow()) % 15 < 14:
                timers.sleep(0.05)
            threading.Thread(target=self.threaded_audio_reader, daemon=True).start()
            threading.Thread(target=self.threaded_spectrum_filler, daemon=True).start()
        threading.Thread(target=self.threaded_decoding_manager, daemon=True).start()
        self.decode_queue = queue.Queue()
        self.decode_workers = []
        num_workers = 10
        for _ in range(num_workers):
            t = threading.Thread(target=self.decode_worker, daemon=True)
            t.start()
            self.decode_workers.append(t)
        with open('success_fail_metrics.log', 'w') as f:
            f.write("{timestamp} {c.decoded} {c.score} {c.llr_sd} {c.snr} {c.n_its} {c.time_in_decode}\n")

    def decode_worker(self):
        """Worker thread: pull candidates off the queue and decode them."""
        while self.running:
            c = self.decode_queue.get()   # waits for a job
            try:
                self.demod.demodulate_candidate(c, self.onResult)
            except Exception as e:
                print("Decode worker error:", e)
            finally:
                self.decode_queue.task_done()

    def find_candidates_from_audio_in(self, audio_in, sync_score_thresh):
        # inject audio e.g. from wav file for testing 
        sample_idx = 0
        while sample_idx < len(audio_in) - self.spectrum.FFT_len:
            self.spectrum.audio_in.extend(audio_in[sample_idx:sample_idx + self.spectrum.FFT_len])
            self.do_FFT(self.spectrum)
            sample_idx += self.demod.samples_perhop
        timers.timedLog(f"[bulk_load_audio] Loaded {self.spectrum.nHops_loaded} hops ({self.spectrum.nHops_loaded/(self.demod.sigspec.symbols_persec * self.demod.hops_persymb):.2f}s)", logfile = 'decodes.log', )
        self.demod.find_candidates(self.spectrum, False, self.onCandidate_found, sync_score_thresh)

    def threaded_audio_reader(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16,
                         channels=1,
                         rate=self.demod.sample_rate,
                         input=True,
                         input_device_index = self.input_device_idx,
                         frames_per_buffer=self.demod.samples_perhop,
                         stream_callback=None)
        
        while self.running:
            data = stream.read(self.demod.samples_perhop, exception_on_overflow=False)
            self.audio_queue.put(data)

    def threaded_spectrum_filler(self):
        self.spectrum = Spectrum(self.demod)
        while self.running:
            cycle_time = timers.tnow() % 15
            # cycle rollover
            if (cycle_time < self.last_cycle_time):
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}: ")
                if(self.verbose): timers.timedLog(f"All cands = {len(self.cands_to_decode)} "
                                +f"\n This cycle: candidates = {self.spectrum.n_candidates} decodes = {self.spectrum.n_decodes}"
                                +f"({100*self.spectrum.n_decodes/(self.spectrum.n_candidates+.01):.0f}%)", logfile = 'decodes.log')
                if(cycle_time > 0.05):
                    self.sync_score_thresh *= 1.1
                    if(self.verbose): timers.timedLog(f"[cycle_manager] Adjust threshold UP to {self.sync_score_thresh:.2f})", logfile = 'decodes.log', silent = False)
                if (self.onOccupancy):
                    self._make_occupancy_array(self.spectrum)
                self.spectrum = Spectrum(self.demod)
            self.last_cycle_time = cycle_time
            # send audio for FFT
            audio_samples = np.frombuffer(self.audio_queue.get(), dtype=np.int16)
            self.spectrum.audio_in.extend(audio_samples)
            self.do_FFT(self.spectrum)

    def do_FFT(self, spectrum):
        FFT_start_sample_idx = int(len(self.spectrum.audio_in) - self.spectrum.FFT_len)
        if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
            aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len]
            aud *= self.time_window
            self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
        self.spectrum.nHops_loaded +=1

    def threaded_decoding_manager(self):
        while self.running:
            
            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop):
                if (not self.spectrum.searched):
                    self.spectrum.searched = True
                    self.demod.find_candidates(self.spectrum, self.prioritise_Hz, self.onCandidate_found, self.sync_score_thresh)
                    
            if (self.spectrum.nHops_loaded > self.spectrum.start_decoding_after_hop):   
                self.cands_to_decode.sort(key=lambda c: -c.score)

                t = timers.tnow()
                with self.cand_lock:
                    stale = [c for c in self.cands_to_decode
                             if (not c.sent_for_decode and (t - c.created_at) > self.max_lifetime)]
                    for c in stale:
                        self.cands_to_decode.remove(c)
                if stale:
                    if(self.verbose): timers.timedLog(f"[prune] removed {len(stale)} stale candidates")

                with self.cand_lock:  
                    send_for_decode = [c for c in self.cands_to_decode
                                       if (not c.sent_for_decode and self.spectrum.nHops_loaded > c.last_data_hop)]
                for c in send_for_decode:
                    c.sent_for_decode = True
                    self.decode_load +=1
                    self.decode_queue.put(c)

            n_cands = len(self.cands_to_decode)
            send_to_ui_ws("decode_queue", {'n_candidates':n_cands, 'parallel_decodes':self.decode_load})    
            timers.sleep(0.25)

    def onCandidate_found(self, c):
        c.created_at = timers.tnow()
        self.cands_to_decode.append(c)
        
    def onResult(self,c):
        metrics = f"{c.decoded:>7} {c.score:7.2f} "
        metrics = metrics + f"{c.llr_sd:7.2f} {c.snr:7.1f} "
        metrics = metrics + f"{c.n_its:7.1f} {c.time_in_decode:7.3f}"
        if(self.verbose): timers.timedLog(metrics, logfile='success_fail_metrics.log', silent = True)
        c_decoded = c if(c.decode_dict) else None
        self.cands_to_decode.remove(c)
        self.decode_load -=1
        if(c_decoded):
            if(self.sync_score_thresh > c.score * 0.9):
                self.sync_score_thresh = c.score * 0.9
                if(self.verbose): timers.timedLog(f"[cycle_manager] Adjust threshold DOWN to {self.sync_score_thresh:.2f})", logfile = 'decodes.log', silent = False)
            self.onDecode(c_decoded)
 
    def _make_occupancy_array(self, spectrum, f0=0, f1=3500, bin_hz=10, sig_hz = 50):
        if(not spectrum): return
        occupancy = np.arange(f0, f1 + bin_hz, bin_hz)
        for c in spectrum.candidates:
            bin0 = int((c.origin_physical[1]-f0)/bin_hz)
            bin1 = bin0 + int(sig_hz/bin_hz)
            occupancy[bin0:bin1] = occupancy[bin0:bin1] + c.max_pwr
        occupancy = occupancy/np.max(occupancy)
        fs0, fs1 = 1000,1500
        bin0 = int((fs0-f0)/bin_hz)
        bin1 = int((fs1-f0)/bin_hz)
        clear_freq = fs0 + bin_hz*np.argmin(occupancy[bin0:bin1])
        occupancy = 10*np.log10(occupancy + 1e-12)
        occupancy = 1 + np.clip(occupancy, -40, 0) / 40
        self.onOccupancy(occupancy, clear_freq)
