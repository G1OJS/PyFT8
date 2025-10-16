import os
import time
import numpy as np
import pyaudio
import wave
import threading
from src.FT8_demodulator import FT8Demodulator
from src.FT8_decoder import FT8_decode
from src.waterfall import Waterfall
from src.test_utils import wsjtx_tailer, wsjtx_compare

SAMPLE_RATE = 12000
CYCLE = 15.0
SHORT_CYCLE = 14.5
FRAMES_PER_CYCLE = int(SAMPLE_RATE * SHORT_CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'

pya = pyaudio.PyAudio()

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
    print(f"{tstrNow()} Audio capture thread running...")
    while True:
        print(f"{tstrNow()} Audio capture waiting for cycle start\n")
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

threading.Thread(target=audioloop).start()
threading.Thread(target=wsjtx_tailer).start()

demod = FT8Demodulator()
wf = Waterfall(demod.specbuff)
t = time.time()

while True:
    print(f"{tstrNow()} Decoder waiting for audio file")
    while not os.path.exists(FLAG_FILE):
        time.sleep(0.1)
    timestr = tstrNow()
    audio = read_wav(BRIDGE_FILE)
    os.remove(FLAG_FILE)
    print(f"{tstrNow()} Decoder has read audio file")
    demod.specbuff.load_TFGrid(audio)
    candidates = demod.get_candidates(topN=25)
    print(f"{tstrNow()} Decoder found {len(candidates)} candidates")
    wf.update(demod.specbuff, candidates = candidates, title = f"FT8 Waterfall {timestr}")
    print(f"{timestr} -------------")
    demod.demodulate(candidates)
    output = FT8_decode(candidates, ldpc = False)
    for l in output:
        print(l)
    wsjtx_compare(output)
