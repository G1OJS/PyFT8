import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.rx.FT8_demodulator import FT8Demodulator, Spectrum
from PyFT8.rx.waterfall import Waterfall
import pyaudio

class Cycle_decoder:
    def __init__(self, onDecode, onOccupancy, prioritise_rxfreq = True):
        self.last_cycle_time = 16
        self.demod = FT8Demodulator()
        self.onDecode = onDecode
        self.onOccupancy = onOccupancy
        self.prioritise_rxfreq = prioritise_rxfreq
        input_device_idx = audio._find_device(config.soundcards['input_device'])   
        threading.Thread(target = audio.read_from_soundcard_chunked,
                         kwargs=({'input_device_idx':input_device_idx, 'samples':384, 'callback':self.cycle_decoder_audio_cb })).start()

    def cycle_decoder_audio_cb(self, in_data, frame_count, time_info, status):
        cycle_time = int(timers.tnow()) %15
        if(cycle_time < self.last_cycle_time):
            self.spectrum = Spectrum(self.demod)
        self.last_cycle_time = cycle_time
        data = np.frombuffer(in_data, dtype=np.int16)
        self.spectrum.audio_in.extend(data)
        FFT_start_sample_idx = int(self.spectrum.nHops_loaded * self.spectrum.samples_perhop - self.spectrum.FFT_len)
        if(FFT_start_sample_idx >0 and self.spectrum.nHops_loaded < self.spectrum.hops_percycle):
            aud = self.spectrum.audio_in[FFT_start_sample_idx:FFT_start_sample_idx + self.spectrum.FFT_len] * np.kaiser(self.spectrum.FFT_len, 14)
            self.spectrum.fine_grid_complex[self.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
            self.spectrum.nHops_loaded = self.spectrum.nHops_loaded
        self.spectrum.nHops_loaded +=1
        
        if(self.spectrum.nHops_loaded > 200 and not self.spectrum.searched):
            self.spectrum.cyclestart_str = timers.cyclestart_str(0)
            prioritise_Hz = config.rxfreq if self.prioritise_rxfreq else False
            if(self.onOccupancy): self._make_occupancy_array(self.spectrum.candidates)
            threading.Thread(target = self.demod.find_candidates, kwargs = ({'spectrum':self.spectrum, 'prioritise_Hz':prioritise_Hz})).start()

        for c in self.spectrum.candidates:
            if(self.spectrum.nHops_loaded > c.last_hop and not(c.decode_tried)):
                threading.Thread(target = self.demod.demodulate_candidate, kwargs = ({'spectrum':self.spectrum, 'candidate':c, 'onDecode':self.onDecode})).start()
  
        return (None, pyaudio.paContinue)


    def _make_occupancy_array(self, candidates, f0=0, f1=3500, bin_hz=10, sig_hz = 50):
        occupancy = np.arange(f0, f1 + bin_hz, bin_hz)
        for c in candidates:
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
