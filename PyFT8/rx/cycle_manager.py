import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum
import pyaudio
import queue

class Cycle_manager():
    def __init__(self, onDecode, onOccupancy, audio_in = [], verbose = True,
                 max_iters = 90, max_stall = 8, max_ncheck = 30,
                 sync_score_thresh = 3, min_sd = 2, max_delay = 3,
                 max_parallel_decodes = 20):
        self.max_parallel_decodes = max_parallel_decodes
        self.verbose = verbose
        self.max_delay = max_delay
        self.live = True
        self.cand_lock = threading.Lock()
        self.last_cycle_time = 1e9
        self.demod = FT8Demodulator(max_iters, max_stall, max_ncheck, sync_score_thresh, min_sd)
        self.running = True
        self.spectrum = Spectrum(self.demod)
        self.spectrum.nHops_loaded = 0
        self.decode_load = 0
        self.time_window = np.kaiser(self.spectrum.FFT_len, 20)
        self.onDecode = onDecode
        self.onOccupancy = onOccupancy
        self.candidate_list = []
        self.n_decodes = 0
        self.input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=50)
        # audio_in is e.g. from wav file for testing, otherwise start monitoring sound card
        if(any(audio_in)):
            self.find_candidates_from_audio_in(audio_in)
        else:
            cs = self.demod.sigspec.cycle_seconds 
            while int(timers.tnow()) % cs < (cs-1):
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
            f.write("timestamp   id   decoded   score   llr_sd   snr   n_its   time_in_decode\n")

    def decode_worker(self):
        """Worker thread: pull candidates off the queue and decode them."""
        while self.running:
            c = self.decode_queue.get()   # waits for a job
            try:
                self.demod.demodulate_candidate(c, self.onDecodeResult)
            except Exception as e:
                print("Decode worker error:", e)
            finally:
                self.decode_queue.task_done()

    def find_candidates_from_audio_in(self, audio_in):
        # inject audio e.g. from wav file for testing 
        sample_idx = 0
        self.live = False
        while sample_idx < len(audio_in) - self.spectrum.FFT_len:
            timers.sleep(0.01)
            with self.spectrum.grid_lock:
                self.spectrum.audio_in.extend(audio_in[sample_idx:sample_idx + self.spectrum.FFT_len])
                self.do_FFT(self.spectrum)
                sample_idx += self.demod.samples_perhop
        self.audio_loaded_at = timers.tnow()
        timers.timedLog(f"[bulk_load_audio] Loaded {self.spectrum.nHops_loaded} hops ({self.spectrum.nHops_loaded/(self.demod.sigspec.symbols_persec * self.demod.hops_persymb):.2f}s)", logfile = 'decodes.log', )

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
            cycle_time = timers.tnow() % self.demod.sigspec.cycle_seconds 
            # cycle rollover
            if (self.live and cycle_time < self.last_cycle_time):
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}")
                self.spectrum = Spectrum(self.demod)
            self.last_cycle_time = cycle_time
            # send audio for FFT
            audio_samples = np.frombuffer(self.audio_queue.get(), dtype=np.int16)
            with self.spectrum.grid_lock:
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
            ready_for_demap = []
            
            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop and not self.spectrum.searched):
                self.spectrum.searched = True
                self.demod.find_candidates(self.spectrum, self.onCandidate_found)
                if (self.onOccupancy):
                    self._make_occupancy_array(self.spectrum)

            if (self.spectrum.nHops_loaded > self.spectrum.start_decoding_after_hop):
                with self.cand_lock:
                    ready_for_demap = [c for c in self.candidate_list
                                if self.spectrum.nHops_loaded > c.last_data_hop and not c.demapped]
                    
            for c in ready_for_demap:
                c.frozen_at_hop = self.spectrum.nHops_loaded            
                c.fine_grid_complex_full = c.fine_grid_complex # ensure c has a copy of spectrum
                self.demod.demap_candidate(c)
                c.demapped = True

            with self.cand_lock:
                self.candidate_list =   [c for c in self.candidate_list
                                            if (c.good_llr_sd or not c.demapped)]
                ready_for_decode =      [c for c in self.candidate_list
                                            if timers.tnow() < c.expiry_time
                                            and c.good_llr_sd
                                            and not c.sent_for_decode]
                
                ready_for_decode.sort(key=lambda c: -c.llr_sd - 100*(np.abs(c.origin_physical[1]-config.rxfreq)<2))
                for c in ready_for_decode:
                    if(self.decode_load < self.max_parallel_decodes):
                        self.decode_load +=1
                        c.sent_for_decode = True
                        self.decode_queue.put(c)

            loading_info = {'n_candidates':len(self.candidate_list),
                            'parallel_decodes':self.decode_load}
            send_to_ui_ws("decode_queue", loading_info)             
            timers.sleep(0.25)

    def onCandidate_found(self, c):
        with self.cand_lock:  
            c.created_at = timers.tnow()
            c.expiry_time = 15*int(c.created_at/15) + 15 + self.max_delay
            self.candidate_list.append(c)
            
    def onDecodeResult(self,c):
        with self.cand_lock: 
            if(self.verbose): 
                metrics = f"{c.id} {c.decoded:>7} {c.score:7.2f} {c.llr_sd:7.2f} {c.snr:7.1f} {c.n_its:7.1f} {c.time_in_decode:7.3f}"
                timers.timedLog(metrics, logfile='success_fail_metrics.log', silent = True)
            if c in self.candidate_list:
                self.candidate_list.remove(c)
            self.decode_load -=1
            if(timers.tnow() > c.expiry_time):
                timers.timedLog(f"Expired candidate {c.id} returned by ldpc ({timers.tnow()} > {c.expiry_time})" , logfile='success_fail_metrics.log', silent = True)                
        if(c.decoded):
            self.n_decodes +=1
            self.onDecode(c)
 
    def _make_occupancy_array(self, spectrum, f0=0, f1=3500, bin_hz=10):
        if(not spectrum): return
        occupancy_fine = spectrum.occupancy/np.max(spectrum.occupancy)
        n_out = int((f1-f0)/bin_hz)
        occupancy = np.zeros(n_out)
        for i in range(n_out):
            occupancy[i] = occupancy_fine[int((f0+bin_hz*i)/spectrum.df)]
        fs0, fs1 = 1000,1500
        bin0 = int((fs0-f0)/bin_hz)
        bin1 = int((fs1-f0)/bin_hz)
        clear_freq = fs0 + bin_hz*np.argmin(occupancy[bin0:bin1])
        occupancy = 10*np.log10(occupancy + 1e-12)
        occupancy = 1 + np.clip(occupancy, -40, 0) / 40
        self.onOccupancy(occupancy, clear_freq)
