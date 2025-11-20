import threading
import numpy as np
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import pyaudio

class Cycle_decoder:

    def __init__(self, onDecode, onOccupancy, prioritise_rxfreq = True):
        self.audio_in = []
        self.demod = FT8Demodulator()
        self.onDecode = onDecode
        self.onOccupancy = onOccupancy
        self.prioritise_rxfreq = prioritise_rxfreq
        self.nHops_loaded = 0
        self.duplicate_filter = set()
        self.samples_perhop = 384
        self.hops_percycle = 467
        threading.Thread(target = self.cycle_decoder).start()

    def cycle_decoder(self):
        input_device_idx=audio._find_device(config.soundcards['input_device'])
        self.init_cycle()
        audio.read_from_soundcard_chunked(384, self.cycle_decoder_audio_cb)

    def init_cycle(self):
        print("Wait for new Cycle\n")
        self.duplicate_filter = set()
        self.audio_start = timers.tnow() %15;
        self.searched = False
        self.decoded = False
        self.candidates = []
        print(len(self.audio_in))
        while ((timers.tnow() %15) >0.2):
            self.audio_in = []
            self.nHops_loaded = 0
            timers.sleep(0.05)

    def cycle_decoder_audio_cb(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16)
        self.audio_in.extend(data)
        
        self.nHops_loaded +=1
        if(self.nHops_loaded > 300 and not self.searched):
            threading.Thread(target = self._get_candidates, kwargs = ({'audio_in':self.audio_in})).start()
            self.searched = True
        if(self.nHops_loaded > self.hops_percycle and not self.decoded):
            self.decoded = True
            threading.Thread(target = self._get_decodes, kwargs = ({'audio_in':self.audio_in})).start()
            self.init_cycle()
        return (None, pyaudio.paContinue)

    def _get_candidates(self, audio_in):
        cyclestart_str = timers.cyclestart_str(0)
        self.demod.load_audio(audio_in)  
        self.candidates = self.demod.find_candidates(cyclestart_str, prioritise_Hz = config.rxfreq if self.prioritise_rxfreq else False)

    def _get_decodes(self, audio_in):
        if(self.onOccupancy):
            occupancy, clear_freq = self._make_occupancy_array(candidates)
            self.onOccupancy(occupancy, clear_freq)
        if(self.onDecode):
            for c in self.candidates:
                threading.Thread(target = self._decode_candidate, kwargs = ({'c':c})).start()

    def _decode_candidate(self, c):
        decode = self.demod.demodulate_candidate(c, silent = True)
        if(decode):
            decode_dict = decode['decode_dict']
            key = f"{decode_dict['call_a']}{decode_dict['call_b']}{decode_dict['grid_rpt']}"
            if(not key in self.duplicate_filter):
                self.duplicate_filter.add(key)
                dt = c.origin_physical[0] + self.audio_start - 0.3
                dt = f"{dt:4.1f}"
                decode_dict.update({'dt': dt})
                self.onDecode(decode)

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
        return occupancy, clear_freq
