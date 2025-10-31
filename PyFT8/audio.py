import numpy as np
import wave
import pyaudio
from PyFT8.comms_hub import config, events
import PyFT8.timers as timers


global out_device_idx, in_device_idx
out_device_idx, in_device_idx = None, None

def find_device(device_str_contains):
    pya = pyaudio.PyAudio()
    for dev_idx in range(pya.get_device_count()):
        name = pya.get_device_info_by_index(dev_idx)['name']
        match = True
        for pattern in device_str_contains:
            if (not pattern in name): match = False
        if(match):
            timers.timedLog(f"Found device {name} index {dev_idx}")
            return dev_idx
    timers.timedLog(f"No audio device found matching {device_str_contains}")

def read_from_soundcard(device_str_contains, seconds, sample_rate = 12000):
    pya = pyaudio.PyAudio()
    global in_device_idx
    if(not in_device_idx):
        in_device_idx = find_device(device_str_contains)
    timers.timedLog("Audio module opening stream")
    stream = pya.open(format=pyaudio.paInt16, channels = 1, rate = sample_rate,
                      input=True, input_device_index = in_device_idx,
                      frames_per_buffer = seconds * sample_rate)
    data = np.frombuffer(stream.read(sample_rate * seconds, exception_on_overflow=False), dtype=np.int16)
    stream.close()
    return data

def play_wav_to_soundcard(device_str_contains, filename = 'out.wav'):
    global out_device_idx
    if(not out_device_idx):
        out_device_idx = find_device(device_str_contains)
    with wave.open(filename, 'rb') as wf:
        def callback(in_data, frame_count, time_info, status):
            data = wf.readframes(frame_count)
            return (data, pyaudio.paContinue)
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True,
                        stream_callback=callback,
                        output_device_index = out_device_idx)
        while stream.is_active():
            time.sleep(0.1)
        stream.close()
        p.terminate()

def create_ft8_wave(symbols, fs=12000, f_base=1500.0, f_step=6.25):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    waveform = np.concatenate([
        np.sin(2 * np.pi * (f_base + s * f_step) * t)
        for s in symbols
    ])
    waveform = waveform.astype(np.float32)
    waveform_int16 = np.int16(waveform / np.max(np.abs(waveform)) * 32767)
    waveform = waveform / np.max(np.abs(waveform))
    waveform *= 0.5
    return waveform

def write_wav_file(filename, data, sample_rate = 12000):
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setframerate(sample_rate)
    wavefile.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
    wavefile.writeframes(b''.join(data))
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

