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
        self.demod = FT8Demodulator(sigspec, max_iters, max_stall, max_ncheck)
        self.spectrum = Spectrum(self.demod)
        self.running = True
        self.time_window = np.kaiser(self.spectrum.FFT_len, 20)
        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy
        self.cands_list = []
        self.input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=200)
        self.n_ldpcd = 0
        self.n_decoded = 0
        self.n_unique = 0
        
        # audio_in is e.g. from wav file for testing, otherwise start monitoring sound card
        if(any(audio_in)):
            self.live = False
            self.find_candidates_from_audio_in(audio_in)
        else:
            while (timers.tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds -1 :
                timers.sleep(0.1)
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
        with open('success_fail_metrics.csv', 'w') as f:
            f.write("timestamp,  	       id,   decoded, sync_score,snr,llr_sd, n_its\n")
        with open('success_fail_counts.csv', 'w') as f:
            f.write("timestamp,   	  n_synced, to_demap, demapped, to_ldpc, ldpc'd, decoded, unique, ldpc_%\n")

    def find_candidates_from_audio_in(self, audio_in):
        # inject audio e.g. from wav file for testing 
        sample_idx = 0
        self.live = False
        while sample_idx < len(audio_in) - self.spectrum.FFT_len:
            timers.sleep(0.01)
            with self.spectrum_lock:
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
            if (self.live and cycle_time < self.last_cycle_time):
                self.spectrum.cycle_start_offset = cycle_time
                timers.timedLog(f"Cycle rollover {cycle_time:.2f}")
                self.spectrum.reset(cycle_time)
                self.n_ldpcd = 0
                self.n_decoded = 0
                self.n_unique = 0
            self.last_cycle_time = cycle_time
            audio_samples = np.frombuffer(self.audio_queue.get(), dtype=np.int16)
            with self.spectrum_lock:
                self.spectrum.audio_in.extend(audio_samples)    
                self.do_FFT(self.spectrum)

    def do_FFT(self, spectrum):
        FFT_start_sample_idx = int(len(self.spectrum.audio_in) - self.spectrum.FFT_len)
        if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
            aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len]
            aud *= self.time_window
            self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
        self.spectrum.nHops_loaded +=1

    def fill_candidate(self, candidate):
        c = candidate
        origin = c.sync_result['origin']
        with self.spectrum_lock:
            c.synced_grid_complex = self.spectrum.fine_grid_complex[origin[0]:origin[0]+c.size[0], origin[1]:origin[1]+c.size[1]].copy()

    def threaded_decoding_manager(self):
        while self.running:

            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop and not self.spectrum.searched):
                timers.timedLog("Search spectrum ...")
                with self.spectrum_lock:
                    self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[:self.spectrum.candidate_search_after_hop,:].copy()
                self.demod.find_syncs(self.spectrum, self.sync_score_thresh, self.onFindSync)
                timers.timedLog("Spectrum searched")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy)
                self.spectrum.searched = True

            cands_to_demap = []
            if(self.spectrum.searched):
                with self.cands_list_lock:
                    cands_synced = [c for c in self.cands_list if c.sync_result]
                cands_to_demap = [c for c in cands_synced
                                  if self.spectrum.nHops_loaded > c.sync_result['last_data_hop']
                                  and not c.demap_requested]
            
            for c in cands_to_demap:
                c.demap_requested = True
                self.fill_candidate(c)
                self.demod.demap_candidate(self.spectrum, c)
                if(c.demap_result['llr_sd'] < self.llr_sd_thresh):
                    with self.cands_list_lock:
                        self.cands_list.remove(c)
                    
            with self.cands_list_lock:
                demapped = [c for c in self.cands_list if c.demap_result]
                
            cands_for_ldpc = [c for c in demapped
                              if c.demap_result['llr_sd'] > self.llr_sd_thresh
                              and not c.ldpc_requested]
            cands_for_ldpc.sort(key=lambda c: -c.demap_result['llr_sd'] - 100*(np.abs(c.sync_result['origin'][3]-config.rxfreq)<2))
            for c in cands_for_ldpc:
                c.ldpc_requested = True
                self.decode_queue.put(c)

            stats = {
                'n_synced': len(self.cands_list),
                'n_pending_demap': len(cands_to_demap),
                'n_demapped': len(demapped),
                'n_pending_ldpc': len(cands_for_ldpc),
                'n_ldpcd': self.n_ldpcd,
                'n_decoded': self.n_decoded,
                'n_unique': self.n_unique,
                'ldpc_success%': self.n_decoded/(self.n_ldpcd+.0001)
            }
            timers.timedLog(', ' + ', '.join([f"{v:>6}" for k, v in stats.items()]), logfile='success_fail_counts.csv', silent = True)
     
            loading_info = {'n_candidates': stats['n_synced'],
                            'parallel_decodes': self.decode_queue.qsize()}
            send_to_ui_ws("decode_queue", loading_info)
            timers.sleep(0.01)

    def onFindSync(self, sync_result):
        c = Candidate(self.spectrum)
        c.sync_result = sync_result
        with self.cands_list_lock:
            self.cands_list.append(c)

    def decode_worker(self):
        while self.running:
            c = self.decode_queue.get()
            try:
                self.demod.decode_candidate(c, self.onDecode)
            except Exception as e:
                print("Decode worker error:", e)
            finally:
                self.decode_queue.task_done()
            
    def onDecode(self, c):
        with self.cands_list_lock:
            self.cands_list.remove(c)
        self.n_ldpcd +=1
        decoded = not (c.decode_result == None)
        if(self.verbose):
            metrics = f"{c.id} {decoded:>7} {c.sync_result['sync_score']:7.2f} {c.demap_result['snr']:7.1f} {c.demap_result['llr_sd']:7.2f} {c.ldpc_result['n_its']:7.1f}"
            timers.timedLog(metrics, logfile='success_fail_metrics.csv', silent = True)
        if(decoded):
            self.n_decoded +=1
            origin = c.sync_result['origin']
            #dt = origin[2] - self.spectrum.cycle_start_offset - 0.3 -0.5
            dt = origin[2]
            if(dt > self.sigspec.cycle_seconds//2): dt -=self.sigspec.cycle_seconds
            dt = f"{dt:4.1f}"
            c.decode_result.update({'dt': dt})
            key = f"{c.decode_result['call_a']} {c.decode_result['call_b']} {c.decode_result['grid_rpt']}"
            if(not key in self.spectrum.duplicate_filter):
                self.n_unique +=1
                self.spectrum.duplicate_filter.add(key)
                self.onSuccessfulDecode(c)

 
