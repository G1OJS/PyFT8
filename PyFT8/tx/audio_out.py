import numpy as np
import wave
import pyaudio
import sys
import time

def create_ft8_wave(symbols, filename = 'out.wav', fs=12000, f_base=1500.0, f_step=6.25):
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
    with wave.open(filename, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(fs)
        f.writeframes(waveform_int16.tobytes())

def play_ft8_wave(filename = 'out.wav'):
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        name = p.get_device_info_by_index(i)['name']
        if('Speakers' in name and 'CODEC' in name):
       # if('Speakers' in name and 'High' in name):
            dev_idx = i
            break
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
                        output_device_index = dev_idx)
        while stream.is_active():
            time.sleep(0.1)
        stream.close()
        p.terminate()
    



