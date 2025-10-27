import os
import time
import numpy as np
import pyaudio
import wave
import threading
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall

SAMPLE_RATE = 12000
CYCLE = 15.0
SHORT_CYCLE = 14
FRAMES_PER_CYCLE = int(SAMPLE_RATE * SHORT_CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'
PyFT8_file = "pyft8.txt"
wsjtx_file = "wsjtx.txt"
pya = pyaudio.PyAudio()

def tstrcyclestart_str(cycle_offset):
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(15*cycle_offset + 15*int(time.time() / 15)))

def tstrNow():
    return time.strftime("%H:%M:%S", time.gmtime(time.time()))

def dumpwav(filename, data):
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setframerate(SAMPLE_RATE)
    wavefile.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
    wavefile.writeframes(b''.join(data))
    wavefile.close()

def audioloop():
    while True:
        t = time.time()
        t_to_next = CYCLE - (t % CYCLE)
        time.sleep(t_to_next)
        stream = pya.open(format=pyaudio.paInt16, channels = 1, rate=SAMPLE_RATE,
                      input=True, input_device_index = 1,
                      frames_per_buffer=FRAMES_PER_CYCLE)
        data = np.frombuffer(stream.read(FRAMES_PER_CYCLE, exception_on_overflow=False), dtype=np.int16)
        dumpwav(BRIDGE_FILE, data)
        stream.close()
        with open(FLAG_FILE, 'w') as f: f.write("x")

def read_wav(filename, sample_rate = 12000):
     import wave
     import numpy as np
     with wave.open(filename, 'rb') as wav:
          assert wav.getframerate() == sample_rate
          assert wav.getnchannels() == 1
          assert wav.getsampwidth() == 2
          audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
     return audio

global demod
threading.Thread(target=audioloop).start()
demod = FT8Demodulator(sample_rate=12000, fbins_pertone=3, hops_persymb=3)

def run():
    import json
    while True:
        while not os.path.exists(FLAG_FILE):   
            time.sleep(.1)
        cycle_str = tstrcyclestart_str(1)
        audio = read_wav(BRIDGE_FILE)
        os.remove(FLAG_FILE)
        print(f"{tstrNow()} start demod")
        demod.spectrum.feed_audio(audio)
        candidates = demod.find_candidates(topN=10)
        print(f"{tstrNow()} Candidates: {len(candidates)}")
        decodes = demod.demodulate(candidates, cyclestart_str = cycle_str)
        print(f"{tstrNow()} Decodes: {len(decodes)}")
        with open("data.json", "w") as f:
            json.dump(decodes, f)

