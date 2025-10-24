import os
import time
import numpy as np
import pyaudio
import wave
import threading
import sys
import ast
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall

SAMPLE_RATE = 12000
CYCLE = 15.0
SHORT_CYCLE = 14.6
FRAMES_PER_CYCLE = int(SAMPLE_RATE * SHORT_CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'
PyFT8_file = "pyft8.txt"
wsjtx_file = "wsjtx.txt"
pya = pyaudio.PyAudio()

def wsjtx_tailer():
    cycle = ''
    def follow(path):
        with open(path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()

    for line in follow(r"C:\Users\drala\AppData\Local\WSJT-X\ALL.txt"):
        wsjtx_file = f"wsjtx.txt"
        with open(wsjtx_file, 'a') as f:
                f.write(f"{line}\n")
           
def wsjtx_compare(wsjtx_file, PyFT8_file):
    PyFT8_patterns, wsj_patterns = set(), set()
    matched_msgs, unmatched_msgs = [],[]
        
    with open(wsjtx_file, 'r') as f:
        wsjt = f.readlines()
    for wsjtline in wsjt:
        l = wsjtline[48:]
        wsj_pattern = l.replace(' ','').replace('\n','')
        wsj_patterns.add(wsj_pattern)

    with open(PyFT8_file, 'r') as f:
        PyFT8lines = f.readlines()
    for PyFT8line in PyFT8lines:
        l = d = ast.literal_eval(PyFT8line)['msg']
        PyFT8_pattern = l.replace(' ','')
        if(PyFT8_pattern in wsj_patterns):
            matched_msgs.append(l)
        else:
            unmatched_msgs.append(l)
        PyFT8_patterns.add(PyFT8_pattern)

    matches = PyFT8_patterns.intersection(wsj_patterns)
    PyFT8_only = PyFT8_patterns.difference(wsj_patterns)
    PyFT8 = len(PyFT8_patterns)
    wsj = len(wsj_patterns)
    both = len(matches)
    PyFT8_only = len(PyFT8_only)
    pc = PyFT8/wsj if wsj>0 else 0
    print(f"wsjt: {wsj} PyFT8: {PyFT8} ({pc:.1%}) matched: {both} unmatched: {PyFT8_only}")

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

def reset_compare():
    with open(wsjtx_file, 'w') as f:
        f.write("")
    with open(PyFT8_file, 'w') as f:
        f.write("")

demod = FT8Demodulator(sample_rate=12000, fbins_pertone=3, hops_persymb=3)
wf = Waterfall(demod.spectrum, f1=3500)

no_decodes_before = True
while True:
    print(f"{tstrNow()} Decoder waiting for audio file")
    while not os.path.exists(FLAG_FILE):
        time.sleep(0.1)
    cyclestart_str = tstrcyclestart_str(0)
    audio = read_wav(BRIDGE_FILE)
    os.remove(FLAG_FILE)
    print(f"{tstrNow()} Demodulator has read audio file")
    demod.spectrum.feed_audio(audio)
    
    candidates = demod.find_candidates(topN=40)
    print(f"Found {len(candidates)} candidates")
    wf.update_main(candidates=candidates, cyclestart_str = cyclestart_str)

    print(f"{cyclestart_str} =================================")
    print("Demodulating")
    decodes = demod.demodulate(candidates, cyclestart_str = cyclestart_str)
    print(f"Decoded {len(decodes)} signals\n")
    wf.show_decodes(decodes)
    
    if(any(decodes) and no_decodes_before):
        no_decodes_before = False
        reset_compare()
    print(f"{tstrNow()} Decoded results:")
    for l in decodes:
        print(f"{l}")
        with open(PyFT8_file, 'a') as f:
            f.write(f"{l}\n")
    wsjtx_compare(wsjtx_file,PyFT8_file)

