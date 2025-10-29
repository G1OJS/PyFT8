import os
import numpy as np
import pyaudio
import time
import wave
import threading
import sys
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

def dumpwav(filename, data):
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setframerate(SAMPLE_RATE)
    wavefile.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
    wavefile.writeframes(b''.join(data))
    wavefile.close()

def audioloop():
    timers.timedLog("Audio capture thread running...")
    while True:
        timers.timedLog("Audio capture waiting for cycle start")
        t_elapsed, t_remaining = timers.time_in_cycle()
        time.sleep(t_remaining-0.25)
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

demod = FT8Demodulator(sample_rate=12000, fbins_pertone= 3, hops_persymb=3)
wf = Waterfall(demod.spectrum, f1=3500)

while True:
    reset_compare()
    timers.timedLog("")
    timers.timedLog("Decoder waiting for audio file")
    while not os.path.exists(FLAG_FILE):
        time.sleep(0.1)
    cycle_str = timers.tstrcyclestart_str(1)
    audio = read_wav(BRIDGE_FILE)
    os.remove(FLAG_FILE)
    timers.timedLog(f"Start to Load audio from {BRIDGE_FILE}")
    demod.spectrum.feed_audio(audio)
    timers.timedLog("Start to Show spectrum")
    wf.update_main()
    timers.timedLog("Start to Find candidates")
    candidates = demod.find_candidates(100,3300, topN=500)
    timers.timedLog(f"Found {len(candidates)} candidates")
    timers.timedLog("Start to deduplicate candidate frequencies")
    candidates = demod.deduplicate_candidate_freqs(candidates, topN=100)
    timers.timedLog(f"Now have {len(candidates)} candidates")
    timers.timedLog("Start to sync candidates")
    candidates = demod.sync_candidates(candidates, topN=30)
    timers.timedLog(f"Synced {len(candidates)} candidates")
    timers.timedLog("Start to Show candidates")
    wf.update_main(candidates=candidates)
    #wf.show_zoom(candidates=candidates[:5])
    timers.timedLog("Start to demodulate candidates")
    decodes = demod.demodulate(candidates, cyclestart_str = cycle_str)
    timers.timedLog(f"Decodes: {len(decodes)}")
        
    with open(PyFT8_file, 'a') as f:
        for l in decodes:
            f.write(f"{l[1]}\n")
    wsjtx_compare(wsjtx_file,PyFT8_file)
    t_elapsed, t_remaining = timers.time_in_cycle()
    timers.timedLog(f"Decodes finished {t_elapsed:4.1f} seconds into cycle")

