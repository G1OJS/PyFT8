import os
import time
import numpy as np
import pyaudio
import wave
import threading
from lib.FT8_demodulator import FT8Demodulator
from lib.FT8_decoder import FT8_decode
from lib.waterfall import Waterfall

SAMPLE_RATE = 12000
CYCLE = 15.0
FRAMES_PER_CYCLE = int(SAMPLE_RATE * CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'

pya = pyaudio.PyAudio()

def dumpwav(filename, data):
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setframerate(SAMPLE_RATE)
    wavefile.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
    wavefile.writeframes(b''.join(data))
    wavefile.close()

def audioloop():
    print("Audio capture thread running...")
    while True:
        t = time.time()
        t_to_next = 15 - (t % 15)
        time.sleep(t_to_next)
        stream = pya.open(format=pyaudio.paInt16, channels = 1, rate=SAMPLE_RATE,
                      input=True, input_device_index = 1,
                      frames_per_buffer=FRAMES_PER_CYCLE)
        data = np.frombuffer(stream.read(FRAMES_PER_CYCLE, exception_on_overflow=False), dtype=np.int16)
        dumpwav(BRIDGE_FILE, data)
        with open(FLAG_FILE, 'w'): pass

def read_wav(filename, chunk_size=1024, sample_rate = 12000):
     import wave
     import numpy as np
     with wave.open(filename, 'rb') as wav:
          assert wav.getframerate() == sample_rate
          assert wav.getnchannels() == 1
          assert wav.getsampwidth() == 2
          audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
     return audio

threading.Thread(target=audioloop).start()

demod = FT8Demodulator()
wf = Waterfall(demod.specbuff)


while True:
    while not os.path.exists(FLAG_FILE):
        time.sleep(0.1)
    audio = read_wav(BRIDGE_FILE)
    os.remove(FLAG_FILE)
    demod.specbuff.load_TFGrid(audio)
    candidates = demod.get_candidates(topN=5)
    wf.update(demod.specbuff, candidates = candidates)
    demod.demodulate(candidates)
    print(FT8_decode(candidates, ldpc = False))
