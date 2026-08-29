import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

import numpy as np
import pickle, threading, pyaudio, sys, queue, os
from PyFT8.time_utils import time_utils
from matplotlib.animation import FuncAnimation
from PyFT8.receiver import Receiver
from PyFT8.transmitter import SoundcardOut
from PyFT8.gui import Gui

finished_audio = False
gui = None

class SoundcardOut:
    def __init__(self, outputcard_keywords, wav_files, wav_file_time_offset = 0):
        self.wav_file_time_offset = wav_file_time_offset
        self.output_device_index = None
        self.pya = pyaudio.PyAudio()
        threading.Thread(target = self.play_wavs, args = (wav_files,), daemon = True).start()
        
        if outputcard_keywords:
            for dev_idx in range(self.pya.get_device_count()):
                name = self.pya.get_device_info_by_index(dev_idx)['name']
                match = True
                for pattern in outputcard_keywords.replace(' ','').split(','):
                    if (not pattern in name): match = False
                if(match):
                    self.output_device_index = dev_idx
                    break
            if not self.output_device_index:
                time_utils.tlog(f"[Audio Out] No output audio device found matching {outputcard_keywords}", verbose = True)
                sys.exit(1)

    def play_wavs(self, wav_files, sr=12000):
        global finished_audio
        import wave
        t = (self.wav_file_time_offset - time_utils.cycle_time()) %15
        time_utils.sleep(t)
        dt = 0.6/4
        for i, w in enumerate(wav_files):
            print(f"Start playing wav file {w}")
            wv = wave.open(w, 'rb')
            audio_bytes = wv.readframes(sr*16)
            audio_bytes = audio_bytes[-int(sr*(15-dt))*2:]

            stream = self.pya.open(format=pyaudio.paInt16, channels=1, rate = sr, output=True,
                              output_device_index = self.output_device_index)
            stream.write(audio_bytes)
            stream.stop_stream()
            stream.close()
        time_utils.sleep(5)
        finished_audio = True

class Wsjtx_all_tailer:
    
    def __init__(self, on_decode, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt", silent = True):
        self.all_file = all_file
        self.on_decode = on_decode
        self.silent = silent
        threading.Thread(target = self.run).start()

    def run(self):
        print("WSJT-x ALL Tailer running")
        def follow():
            with open(self.all_file, "r") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time_utils.sleep(0.2)
                        continue
                    yield line.strip()
        for line in follow():
            ls = line.split()
            msg = ' '.join(ls[7:])
            self.on_decode({'decode_completed':time_utils.time(),  'ws_msg':msg, 'ws_cycle':ls[0]})

py_q = queue.Queue()
ws_q = queue.Queue()

def process_message(m):
    global py_q
    py_q.put(m)
    if gui:
        gui.process_message(m)

def on_wsjtx_decode(m):
    global ws_q
    ws_q.put(m)

def monitor_decodes():
    while not finished_audio:
        time_utils.sleep(5)
        
        while not py_q.empty():
            time_utils.sleep(0)
            m = py_q.get()
            if m['cyclestart_string'] != py_cycle[0]:
                baseline_decode_count = baseline_counts[py_cycle[1]] if py_cycle[1] < len(baseline_counts) else 0
                py_cycle[0] = m['cyclestart_string']
                py_cycle[1] += 1
            py_times.append(float(m['decode_completed']) - t_start)
            decode_notes = m['decode_notes']
            decode_count = len(py_times)
            diff = decode_count - baseline_decode_count
            py_info  = f"{decode_count:03d}({diff:+03d}) {py_cycle[1]:03d} {py_times[-1]:7.2f} {decode_notes:30s} {m['all_txt_format']}"
            with open('PyFT8.txt', 'a') as f:
                f.write(f"{py_info}\n")
            print(py_info)
            
        while not ws_q.empty():
            time_utils.sleep(0)
            m = ws_q.get()
            wst = float(m['decode_completed']) - t_start
            if m['ws_cycle'] != ws_cycle[0]:
                ws_cycle[0] = m['ws_cycle']
                ws_cycle[1] += 1
            if len(py_times):
                if wst > py_times[0] - 5:
                    ws_times.append(wst)
                    decode_count = len(ws_times)
                    ws_info  = f"{decode_count:03d} {ws_cycle[1]:3d} {ws_times[-1]:7.2f} ~ {m['ws_msg']}"
                    with open('wsjtx.txt', 'a') as f:
                        f.write(f"{ws_info}\n")
                   # print(ws_info)


def do_test(input_device_keywords, wav_range = None):
    global t_start, gui, ws_cycle, py_cycle
    global baseline_counts, py_times, ws_times
    ws_cycle = ['', 0]
    py_cycle = ['', 0]

    with open('PyFT8.txt','w') as f:
        f.write('')
    with open('wsjtx.txt','w') as f:
        f.write('')
    baseline_counts = []
    
    if os.path.exists(baseline_file):
        with open(baseline_file, 'r') as f:
            lines = f.readlines()
        cycle_prev = lines[0].split()[1]
        for i, l in enumerate(lines):
            cycle = l.split()[1]
            if cycle != cycle_prev:
                cycle_prev = cycle
                baseline_counts.append(i)
        baseline_counts.append(i)
        print(f"Loaded {len(baseline_counts)} cycle decode counts from {baseline_file}")

    wav_files = []
    if wav_range:
        for idx in range(*wav_range):
            wav_files.append(f"{wav_folder}/test_{idx:02d}.wav")

    wsjtx_all_tailer = Wsjtx_all_tailer(on_wsjtx_decode, silent = False)

    if wav_files:
       soundout = SoundcardOut("CABLE, Input", wav_files, wav_file_time_offset = -1)

    t = 15-time_utils.cycle_time()
    if t > 0.05:
        print(f"Waiting to start test on next cycle ({t:6.1f}s)")
        time_utils.sleep(t)
    t_start = time_utils.time()

    py_times, ws_times = [], []

    threading.Thread(target = monitor_decodes, daemon = True).start()
    receiver = Receiver(input_device_keywords, process_message,
                        search_freq_range = [200, 2800])
    if not receiver.audio_in.input_device_idx:
        time_utils.tlog(f"[Audio] No input audio device found matching {input_device_keywords}", verbose = True)
        sys.exit(1)
  #  gui = Gui('G1OJS', 'IO90', None, None, None, {'band':'20m', 'fHz':14074000}, None, receiver.audio_in.waterfall_data, 5, 'km', nodisplay = True) 
  #  gui.start(testing = True)


wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"
baseline_file = 'PyFT8_1_38_baseline.txt'

#do_test("Mic, CODEC")
do_test("CABLE, Output", [1,39])
