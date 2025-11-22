import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config, send_to_ui_ws
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum
from PyFT8.rx.waterfall import Waterfall
import pyaudio
import queue

class Cycle_decoder:
    def __init__(self, onDecode, onOccupancy, prioritise_rxfreq = True):
        self.verbose = False
        self.last_cycle_time = 16
        self.demod = FT8Demodulator()
        self.onDecode = onDecode
        self.onOccupancy = onOccupancy
        self.cands_to_decode = []
        self.prioritise_rxfreq = prioritise_rxfreq
        self.candidate_limit_per_cycle = int(config.decoder_search_limit)
        input_device_idx = audio._find_device(config.soundcards['input_device'])   
        self.audio_queue = queue.Queue(maxsize=50)
        self.running = True
        while int(timers.tnow()) % 15 < 14:
            timers.sleep(0.05)
        threading.Thread(target=self.threaded_audio_reader, daemon=True).start()
        threading.Thread(target=self.threaded_candidate_generator, daemon=True).start()
        threading.Thread(target=self.threaded_decoding_manager, daemon=True).start()

    def threaded_audio_reader(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16,
                         channels=1,
                         rate=self.demod.sample_rate,
                         input=True,
                         frames_per_buffer=self.demod.samples_perhop,
                         stream_callback=None)
        
        while self.running:
            data = stream.read(self.demod.samples_perhop, exception_on_overflow=False)
            self.audio_queue.put(data)

    def threaded_candidate_generator(self):
        self.spectrum = Spectrum(self.demod)
        while self.running:
            audio_samples = self.audio_queue.get()
            cycle_time = int(timers.tnow()) % 15
            # cycle rollover
            if (cycle_time < self.last_cycle_time):
                timers.timedLog(f"Cycle rollover", logfile = 'decodes.log')
                if (self.onOccupancy):
                    threading.Thread( target=self._make_occupancy_array, kwargs={'spectrum': self.spectrum} ).start()
                self.spectrum = Spectrum(self.demod)
            self.last_cycle_time = cycle_time

            # send audio for FFT
            audio_samples = np.frombuffer(audio_samples, dtype=np.int16)
            self.spectrum.audio_in.extend(audio_samples)
            self.do_FFT(self.spectrum)

            # trigger thread to search spectrum for candidates
            if (self.spectrum.nHops_loaded > self.spectrum.candidate_search_after_hop and not self.spectrum.searched):
                self.spectrum.searched = True
                prioritise_Hz = config.rxfreq if self.prioritise_rxfreq else False
                threading.Thread(target=self.demod.find_candidates, kwargs={'spectrum':self.spectrum, 'prioritise_Hz':prioritise_Hz, 'onCandidate_found':self.onCandidate_found}).start()

    def onCandidate_found(self, c):
        self.cands_to_decode.append(c)
        n_cands_to_decode = len([c for c in self.cands_to_decode if not c.sent_for_decode])
        n_cands = len(self.cands_to_decode)
        if(self.verbose): timers.timedLog(f"Add {c.info} to decode pool size: {n_cands} to decode: {n_cands_to_decode}", logfile = 'decodes.log', silent = True)

    def threaded_decoding_manager(self):
        while self.running:
            self.cands_to_decode.sort(key=lambda c: -c.score)
            self.cands_to_decode = self.cands_to_decode[:self.candidate_limit_per_cycle]
            for c in self.cands_to_decode:
                if(not c.sent_for_decode and self.spectrum.nHops_loaded > c.last_data_hop):
                    c.sent_for_decode = True
                    if(self.verbose): timers.timedLog(f"Send {c.info} for decode", logfile = 'decodes.log', silent = True)
                    threading.Thread(target=self.demod.demodulate_candidate, kwargs={'candidate': c, 'onResult': self.onResult}).start()
            n_cands = len([c for c in self.cands_to_decode if not c.sent_for_decode])
            send_to_ui_ws("decode_queue", {'n_candidates':n_cands, 'parallel_decodes':self.demod.decode_load})
            timers.sleep(0.25)

    def onResult(self,c):
        c_decoded = c if(c.decode_dict) else None
        if(self.verbose): timers.timedLog(f"Result for {c.info} {'decoded' if(c.decode_dict) else 'failed'}", logfile = 'decodes.log', silent = True)
        self.cands_to_decode.remove(c)
        if(self.verbose): 
            n_cands_to_decode = len([c for c in self.cands_to_decode if not c.sent_for_decode])
            n_cands = len(self.cands_to_decode)
            timers.timedLog(f"                  pool size: {n_cands} to decode: {n_cands_to_decode}", logfile = 'decodes.log', silent = True)
        if(c_decoded):
            self.onDecode(c_decoded)

    def do_FFT(self, spectrum):
        FFT_start_sample_idx = int(len(self.spectrum.audio_in) - self.spectrum.FFT_len)
        if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
            aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len] * np.kaiser(self.spectrum.FFT_len, 14)
            self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
        self.spectrum.nHops_loaded +=1
 
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
