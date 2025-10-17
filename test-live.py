import os
import time
import numpy as np
import pyaudio
import wave
import threading
from PyFT8.FT8_demodulator import FT8Demodulator
from PyFT8.FT8_decoder import FT8_decode
from PyFT8.waterfall import Waterfall
from PyFT8.test_utils import wsjtx_tailer, wsjtx_compare

SAMPLE_RATE = 12000
CYCLE = 15.0
SHORT_CYCLE = 14.5
FRAMES_PER_CYCLE = int(SAMPLE_RATE * SHORT_CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'
PyFT8_file = "pyft8.txt"
PyFT8_llr_file = "pyft8_llr.txt"
wsjtx_file = "wsjtx.txt"

pya = pyaudio.PyAudio()

def tstrcyclestart_str(cycle_offset):
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime(15*cycle_offset + 15*int(time.time() / 15)))

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

with open(wsjtx_file, 'w') as f:
    f.write("")
with open(PyFT8_file, 'w') as f:
    f.write("")
with open(PyFT8_llr_file, 'w') as f:
    f.write("")    
while True:
    print(f"{tstrNow()} Decoder waiting for audio file")
    while not os.path.exists(FLAG_FILE):
        time.sleep(0.1)
    cyclestart_str = tstrcyclestart_str(0)
    audio = read_wav(BRIDGE_FILE)
    os.remove(FLAG_FILE)
    print(f"{tstrNow()} Demodulator has read audio file")
    demod.specbuff.load_TFGrid(audio)
    candidates = demod.get_candidates(topN=25)
    print(f"{tstrNow()} Demodulator found {len(candidates)} candidates")
    wf.update(demod.specbuff, candidates = candidates, title = f"FT8 Waterfall {cyclestart_str}")
    print(f"{cyclestart_str} =================================")

    """
    print(f"Max power -------------")
    demod.demodulate(candidates)
    print(f"{tstrNow()} Decoded results:")
    output = FT8_decode(candidates, cyclestart_str)
    for line in output:
        print(line)
        with open(PyFT8_file, 'a') as f:
            f.write(f"{line}\n")
    wsjtx_compare(wsjtx_file,PyFT8_file)
    """
    print(f"LLR -------------")
    demod.demodulate(candidates, llr = True, ldpc = False)
    print(f"{tstrNow()} Decoded results:")
    output = FT8_decode(candidates, cyclestart_str)
    for line in output:
        print(line)
        with open(PyFT8_llr_file, 'a') as f:
            f.write(f"{line}\n")
    wsjtx_compare(wsjtx_file,PyFT8_llr_file)

    print(f"LLR and LDPC -------------")
    demod.demodulate(candidates, llr = True, ldpc = True)
    print(f"{tstrNow()} Decoded results:")
    output = FT8_decode(candidates, cyclestart_str)
    for line in output:
        print(line)
        with open(PyFT8_llr_file, 'a') as f:
            f.write(f"{line}\n")
    wsjtx_compare(wsjtx_file,PyFT8_llr_file)

