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

class AudioIn:
    def __init__(self, parent_app, fft_window): # needing parent_app here suggests some code below should move there
        self.parent_app = parent_app
        self.spectrum = parent_app.spectrum
        self.demod = parent_app.demod
        self.samples_perhop = self.demod.samples_perhop
        self.hop_time = self.samples_perhop / self.demod.sample_rate
        self.fft_len = self.spectrum.FFT_len
        self.nFreqs = self.spectrum.nFreqs
        self.fft_window = fft_window
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        
    def stream(self, wav_file = None):
        if(wav_file):
            prev_cycle_time = 0
            wf = None
            while self.parent_app.running:
                cycle_time = time.time() % self.demod.sigspec.cycle_seconds
                rollover = (cycle_time < prev_cycle_time)
                prev_cycle_time = cycle_time
                if(rollover):
                    wf = wave.open(wav_file, 'rb')
                nextHop_time = time.time() + self.hop_time
                while time.time() < nextHop_time:
                    time.sleep(0.001)
                if(wf):
                    frames = wf.readframes(self.samples_perhop)
                    if frames:
                        self.buffer_and_FFT(frames)
        else:
            stream = pya.open(format=pyaudio.paInt16, channels=1, rate=self.demod.sample_rate,
                             input=True, input_device_index = self.parent_app.input_device_idx,
                             frames_per_buffer=self.samples_perhop, stream_callback = self.buffer_and_FFT)
            stream.start_stream()

    def buffer_and_FFT(self, in_data, frame_count = None, time_info = None, status_flags = None):
        samples = np.frombuffer(in_data, dtype=np.int16)
        nsamps = len(samples)
        self.audio_buffer[:-nsamps] = self.audio_buffer[nsamps:]
        self.audio_buffer[-nsamps:] = samples
        audio_for_fft = self.audio_buffer * self.fft_window
        z = np.fft.rfft(audio_for_fft)[:self.nFreqs]
        copy_ptr = self.spectrum.fine_grid_pointer + self.spectrum.hops_percycle
        do_copy = copy_ptr < self.spectrum.fine_grid_complex.shape[0]
        with self.parent_app.spectrum_lock:
            self.spectrum.fine_grid_complex[self.spectrum.fine_grid_pointer, :] = z
            if(do_copy):
                self.spectrum.fine_grid_complex[copy_ptr, :] = z
        self.spectrum.fine_grid_pointer = (self.spectrum.fine_grid_pointer +1) % self.spectrum.hops_percycle
        return (None, pyaudio.paContinue)

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




