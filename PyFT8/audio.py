import numpy as np
import wave
import pyaudio
import time
pya = pyaudio.PyAudio()

def find_device(device_str_contains):
    if(not device_str_contains): #(this check probably shouldn't be needed - check calling code)
        return
    print(f"[Audio] Looking for audio device matching {device_str_contains}")
    for dev_idx in range(pya.get_device_count()):
        name = pya.get_device_info_by_index(dev_idx)['name']
        match = True
        for pattern in device_str_contains:
            if (not pattern in name): match = False
        if(match):
            print(f"[Audio] Found device {name} index {dev_idx}")
            return dev_idx
    print(f"[Audio] No audio device found matching {device_str_contains}")

import time
import wave
import numpy as np
import pyaudio
import threading


class AudioIn:
    def __init__(self, spectrum):

        self.symbol_rate = spectrum.sigspec.symbols_persec
        self.sample_rate = spectrum.sample_rate
        self.hop_rate = self.symbol_rate * spectrum.hops_persymb
        fmax_fft = self.sample_rate/2
        self.fft_len = int(spectrum.fbins_pertone * self.sample_rate // self.symbol_rate)
        fft_out_len = int(self.fft_len/2) + 1
        self.nFreqs = int(fft_out_len * spectrum.max_freq / fmax_fft)
        self.fft_window = fft_window=np.kaiser(self.fft_len, 20)
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self._pa = pyaudio.PyAudio()
        self._running = False
        self.wav_finished = False
        self.hoptimes = []
        self.hops_percycle = int(spectrum.sigspec.cycle_seconds * self.hop_rate)
        self.pgrid_main = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.grid_main_ptr = 0

    def do_fft(self):
        t = time.time()
        x = self.audio_buffer * self.fft_window
        z = np.fft.rfft(x)
        p = z.real*z.real + z.imag*z.imag
        p = p[:self.nFreqs]
        self.hoptimes.append(t)
        self.pgrid_main[self.grid_main_ptr] = p
        self.grid_main_ptr = (self.grid_main_ptr + 1) % self.hops_percycle

    def start_wav(self, wav_path, hop_dt):
        threading.Thread(target = self.play_wav, args = (wav_path, hop_dt), daemon=True).start()
        threading.Thread(target = self.do_fft).start()

    def play_wav(self, wav_path, hop_dt):
        self.hop_dt = hop_dt
        self._running = True
        wf = wave.open(wav_path, "rb")
        next_hop_time = time.time()
        dummy_frames = None
        while self._running:
            frames = wf.readframes(int(self.sample_rate // self.hop_rate))
            if not dummy_frames:
                dummy_frames = frames
            if not frames:
                frames = dummy_frames
                self.wav_finished = True
            now = time.time()
            if now < next_hop_time:
                time.sleep(next_hop_time - now)
            next_hop_time += hop_dt
            self._callback(frames, None, None, None)
            self.do_fft()
        wf.close()

    def start_live(self, input_device_idx, hop_dt):
        self._running = True
        self.hop_dt = hop_dt
        self.stream = self._pa.open(
            format = pyaudio.paInt16, channels=1, rate = self.sample_rate,
            input = True, input_device_index = input_device_idx,
            frames_per_buffer = int(self.sample_rate / self.hop_rate), stream_callback=self._callback,)
        self.stream.start_stream()
        threading.Thread(target = self.live_consumer).start()

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        time.sleep(0.001)
        return (None, pyaudio.paContinue)

    def live_consumer(self):
        next_hop_time = time.time()
        while self._running:
            next_hop_time += self.hop_dt
            now = time.time()
            if now < next_hop_time:
                time.sleep(next_hop_time - now)
            self.do_fft()


class AudioOut:

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
        stream = pya.open(format=pyaudio.paInt16, channels=1, rate=fs,
                          output=True,
                          output_device_index = output_device_idx)
        stream.write(audio_data_int16.tobytes())
        stream.stop_stream()
        stream.close()




