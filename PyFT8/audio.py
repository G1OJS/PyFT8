import numpy as np
import wave
import pyaudio
import time
from PyFT8.FT8_encoder import pack_message

def find_device(device_str_contains):
    if(not device_str_contains): #(this check probably shouldn't be needed - check calling code)
        return
    print(f"[Audio] Looking for audio device matching {device_str_contains}")
    for dev_idx in range(pyaudio.PyAudio().get_device_count()):
        name = pyaudio.PyAudio().get_device_info_by_index(dev_idx)['name']
        match = True
        for pattern in device_str_contains:
            if (not pattern in name): match = False
        if(match):
            print(f"[Audio] Found device {name} index {dev_idx}")
            return dev_idx
    print(f"[Audio] No audio device found matching {device_str_contains}")

class AudioIn:
    def __init__(self, cycle_seconds, hops_percycle, symbol_rate, hops_persymb, fbins_pertone, max_freq):
        self.sample_rate = 12000
        self.samples_perhop = int(self.sample_rate / (symbol_rate * hops_persymb))
        self.fft_len = int(fbins_pertone * self.sample_rate // symbol_rate)
        fft_out_len = int(self.fft_len/2) + 1
        self.nFreqs = int(fft_out_len * max_freq * 2 / self.sample_rate)
        self.fft_window = fft_window=np.hanning(self.fft_len)
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.hoptimes = []
        self.hops_percycle = hops_percycle
        self.pgrid_main = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.grid_main_ptr = 0
        self.grid_main_zero_ptr = 0

    def do_fft(self):
        z = np.fft.rfft(self.audio_buffer * self.fft_window)
        p = z.real*z.real + z.imag*z.imag
        self.hoptimes.append(time.time())
        self.pgrid_main[self.grid_main_ptr] = 10*np.log10(p[:self.nFreqs]+1e-12)
        self.grid_main_ptr = (self.grid_main_ptr + 1) % self.hops_percycle

    def load_wav(self, wav_path):
        wf = wave.open(wav_path, "rb")
        frames = wf.readframes(self.samples_perhop)
        while frames:
            self._callback(frames, None, None, None)
            frames = wf.readframes(self.samples_perhop)
        wf.close()

    def start_live(self, input_device_idx):
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = self.sample_rate,
            input = True, input_device_index = input_device_idx,
            frames_per_buffer = self.samples_perhop, stream_callback=self._callback,)
        self.stream.start_stream()

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        self.do_fft()
        return (None, pyaudio.paContinue)

class AudioOut:

    def create_ft8_symbols(self, tx_msg):
        c1, c2, grid_rpt = tx_msg.split()
        return pack_message(c1, c2, grid_rpt)

    def create_ft8_wave(self, symbols, fs=12000, f_base=873.0, f_step=6.25, amplitude = 0.5):
        symbol_len = int(fs * 0.160)
        t = np.arange(symbol_len) / fs
        phase = 0
        waveform = []
        for s in symbols:
            f = f_base + s * f_step
            phase_inc = 2 * np.pi * f / fs
            w = np.sin(phase + phase_inc * np.arange(symbol_len))
            waveform.append(w)
            phase = (phase + phase_inc * symbol_len) % (2 * np.pi)
        waveform = np.concatenate(waveform).astype(np.float32)
        waveform = waveform.astype(np.float32)
        waveform = amplitude * waveform / np.max(np.abs(waveform))
        waveform_int16 = np.int16(waveform * 32767)
        return waveform_int16

    def write_to_wave_file(self, audio_data, wave_file):
        wavefile = wave.open(wave_file, 'wb')
        wavefile.setframerate(12000)
        wavefile.setnchannels(1)
        wavefile.setsampwidth(2)
        wavefile.writeframes(audio_data.tobytes())
        wavefile.close()

    def play_data_to_soundcard(self, audio_data_int16, output_device_idx, fs=12000):
        stream = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1, rate=fs,
                          output=True,
                          output_device_index = output_device_idx)
        stream.write(audio_data_int16.tobytes())
        stream.stop_stream()
        stream.close()




