import numpy as np
import wave
import pyaudio
from PyFT8.comms_hub import config
import PyFT8.timers as timers
global output_device_idx, input_device_idx
output_device_idx, input_device_idx = None, None
pya = pyaudio.PyAudio()
    
def _find_device(device_str_contains):
    timers.timedLog(f"Looking for audio device matching {device_str_contains}")
    for dev_idx in range(pya.get_device_count()):
        name = pya.get_device_info_by_index(dev_idx)['name']
        match = True
        for pattern in device_str_contains:
            if (not pattern in name): match = False
        if(match):
            timers.timedLog(f"Found device {name} index {dev_idx}")
            return dev_idx
    timers.timedLog(f"No audio device found matching {device_str_contains}")

def find_audio_devices():
    global output_device_idx, input_device_idx
    print(config.data)
    input_device_idx = _find_device(config.data['input_device'])
    output_device_idx = _find_device(config.data['output_device'])
find_audio_devices()

def read_from_soundcard(seconds, sample_rate = 12000):
    timers.timedLog("Audio module opening stream", silent = True)
    stream = pya.open(format = pyaudio.paInt16, channels = 1, rate = sample_rate,
                      input=True, input_device_index = input_device_idx,
                      frames_per_buffer = seconds * sample_rate)
    data = np.frombuffer(stream.read(sample_rate * seconds, exception_on_overflow=False), dtype=np.int16)
    stream.close()
    return data

def play_wav_to_soundcard(sample_rate = 12000, filename = 'out.wav'):
    with wave.open(filename, 'rb') as wf:
        def callback(in_data, frame_count, time_info, status):
            data = wf.readframes(frame_count)
            return (data, pyaudio.paContinue)
        stream = pya.open(format = pyaudio.paInt16, channels = 1, rate = sample_rate,
                        output=True, stream_callback = callback,
                        output_device_index = output_device_idx)
        while stream.is_active():
            timers.sleep(0.1)
        stream.close()

def create_ft8_wave(symbols, fs=12000, f_base=1500.0, f_step=6.25):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    waveform = np.concatenate([
        np.sin(2 * np.pi * (f_base + s * f_step) * t)
        for s in symbols
    ])
    waveform = waveform.astype(np.float32)
    waveform_int16 = np.int16( 0.5 * waveform / np.max(np.abs(waveform)) * 32767)
    return waveform_int16

def write_wav_file(filename, data, sample_rate = 12000):
    wavefile = wave.open(filename, 'wb')
    wavefile.setframerate(sample_rate)
    wavefile.setnchannels(1)
    wavefile.setsampwidth(2)
    wavefile.writeframes(data.tobytes())
    wavefile.close()
    
def read_wav_file(filename = 'audio_in.wav', sample_rate = 12000):
     import wave
     import numpy as np
     with wave.open(filename, 'rb') as wav:
          assert wav.getframerate() == sample_rate
          assert wav.getnchannels() == 1
          assert wav.getsampwidth() == 2
          audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
     return audio

