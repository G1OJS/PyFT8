import os
import time
import numpy as np
import pyaudio
import wave
import threading
import sys
import json
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers

SAMPLE_RATE = 12000
CYCLE = 15.0
SHORT_CYCLE = 14.5
FRAMES_PER_CYCLE = int(SAMPLE_RATE * SHORT_CYCLE)
BRIDGE_FILE = 'audio.wav'
FLAG_FILE = 'audio.txt'
PyFT8_file = "pyft8.txt"
wsjtx_file = "wsjtx.txt"
pya = pyaudio.PyAudio()

global config
def get_config():
    global config
    with open("config.json", "r") as f:
        config = json.load( f) 
get_config()

def dumpwav(filename, data):
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setframerate(SAMPLE_RATE)
    wavefile.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
    wavefile.writeframes(b''.join(data))
    wavefile.close()

def audioloop():
    while True:
        _, t_remain, = timers.time_in_cycle()
        time.sleep(t_remain)
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
        cycle_str = timers.tstrcyclestart_str(1)
        audio = read_wav(BRIDGE_FILE)
        os.remove(FLAG_FILE)
        timers.timedLog("Start to load audio")
        demod.spectrum.feed_audio(audio)
        
        timers.timedLog("Decode Rx frequency")
        global config
        get_config()
        print("Rx freq: ",config['rxFreq'])
        rxFreq_decodes = demod.demod_rxFreq(config['rxFreq'], cycle_str)
        with open("rxFreq_data.json", "w") as f:
            json.dump([d[0] for d in rxFreq_decodes], f)
            
        timers.timedLog("Start to Find candidates")
        candidates = demod.find_candidates(100,3300, topN=500)
        timers.timedLog(f"Found {len(candidates)} candidates")
        timers.timedLog("Start to deduplicate candidate frequencies")
        candidates = demod.deduplicate_candidate_freqs(candidates, topN=100)
        timers.timedLog(f"Now have {len(candidates)} candidates")
        timers.timedLog("Start to sync candidates")
        candidates = demod.sync_candidates(candidates, topN=30)
        timers.timedLog(f"Synced {len(candidates)} candidates")
        decodes = demod.demodulate(candidates, cyclestart_str = cycle_str)
        timers.timedLog(f"Decodes: {len(decodes)}")
        with open("data.json", "w") as f:
            json.dump([d[0] for d in decodes], f)

