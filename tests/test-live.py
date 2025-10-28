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

global lw_tot, lp_tot, best_snr_alltime
lw_tot, lp_tot = 0, 0
best_snr_alltime = 50

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
        with open(wsjtx_file, 'a') as f:
            f.write(f"{line}\n")

def wsjtx_compare(wsjtx_file, PyFT8_file):
    global lw_tot, lp_tot, best_snr_alltime

    import sys
    try:
        color = sys.stdout.shell
    except AttributeError:
        raise RuntimeError("Use IDLE")

    with open(wsjtx_file, 'r') as f:
        wsjt_lines = f.readlines()
    with open(PyFT8_file, 'r') as f:
        PyFT8_lines = f.readlines()

    wsjt_patterns =[]
    for l in wsjt_lines:
        wsjt_patterns.append(l[48:].replace(' ',''))
        
    PyFT8_patterns =[]
    for l in PyFT8_lines:
        PyFT8_patterns.append(l[48:].replace(' ',''))

    best_snr = 50
    for i, l in enumerate(wsjt_lines):
        color.write(f"{l}", "STRING" if(wsjt_patterns[i] in PyFT8_patterns) else "KEYWORD")
        if(wsjt_patterns[i] in PyFT8_patterns):
            snr = int(l[34:37])
            if (snr<best_snr): best_snr = snr

    for i, l in enumerate(PyFT8_lines):
        if(PyFT8_patterns[i] not in wsjt_patterns): 
            color.write(f"{l}", "COMMENT")

    lw, lp = len(wsjt_lines), len(PyFT8_lines)
    lw_tot += lw
    lp_tot += lp
    if(best_snr < best_snr_alltime): best_snr_alltime = best_snr    
    print(f"This Cycle: WSJT-X:{lw} PyFT8:{lp} -> {lp/(1e-12+lw):.0%} best snr = {best_snr}")
    print(f"All cycles: WSJT-X:{lw_tot} PyFT8:{lp_tot} -> {lp_tot/(1e-12+lw_tot):.0%} best snr = {best_snr_alltime}")
    print()

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
    print(f"{tstrNow()} Audio capture thread running...")
    while True:
        print(f"{tstrNow()} Audio capture waiting for cycle start\n")
        t = time.time()
        t_to_next = CYCLE - (t % CYCLE)
        time.sleep(t_to_next-0.25)
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
    
def reset_compare():
    with open(wsjtx_file, 'w') as f:
        f.write("")
    with open(PyFT8_file, 'w') as f:
        f.write("")
        
threading.Thread(target=audioloop).start()
threading.Thread(target=wsjtx_tailer).start()

demod = FT8Demodulator(sample_rate=12000, fbins_pertone=3, hops_persymb=3)
wf = Waterfall(demod.spectrum, f1=3500)

while True:
    reset_compare()
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
  #  wf.show_decodes(decodes)
    
    with open(PyFT8_file, 'a') as f:
        for l in decodes:
            f.write(f"{l[1]}\n")
    wsjtx_compare(wsjtx_file,PyFT8_file)

