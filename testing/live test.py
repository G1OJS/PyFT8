import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

import numpy as np
import time, pickle, threading, pyaudio, sys, os, socket, json
from PyFT8m import Receiver

finished_audio = False
RCVR_SOCK = 2121
t_start = 0

class SoundcardOut:
    def __init__(self, outputcard_keywords, wav_files):
        self.wav_files = wav_files
        self.output_device_index = None
        self.pya = pyaudio.PyAudio()
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
                print(f"[Audio Out] No output audio device found matching {outputcard_keywords}", verbose = True)
                sys.exit(1)

    def start_wavs(self):
        threading.Thread(target = self.play_wavs, daemon = True).start()

    def play_wavs(self, sr=12000):
        global finished_audio
        import wave
        for i, w in enumerate(self.wav_files):
            #print(f"Start playing wav file {w}")
            wv = wave.open(w, 'rb')
            audio_bytes = wv.readframes(sr*16)
            audio_bytes = audio_bytes[-int(sr*(15-0.6/4))*2:]

            stream = self.pya.open(format=pyaudio.paInt16, channels=1, rate = sr, output=True,
                              output_device_index = self.output_device_index)
            stream.write(audio_bytes)
            stream.stop_stream()
            stream.close()
        time.sleep(5)
        finished_audio = True

def monitor_decodes():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', RCVR_SOCK))
    while not finished_audio:
        time.sleep(0.1)
        rx_bytes, addres = sock.recvfrom(1024)
        if rx_bytes:
            msg_dict = json.loads(rx_bytes.decode('utf-8'))
            if msg_dict['mtype'] == 'decode':        
                if msg_dict['cyclestart_string'] != py_cycle[0]:
                    baseline_decode_count = baseline_counts[py_cycle[1]] if py_cycle[1] < len(baseline_counts) else 0
                    py_cycle[0] = msg_dict['cyclestart_string']
                    py_cycle[1] += 1
                py_times.append(float(msg_dict['t_decode']) - t_start)
                decode_count = len(py_times)
                diff = decode_count - baseline_decode_count
                txt = f"{msg_dict['decode_info']:28s} dec:{float(msg_dict['t_decode']) % 15:5.2f} {' '.join(msg_dict['msg_tuple'])}"
                py_info  = f"{decode_count:03d}({diff:+03d}) {py_cycle[1]:03d} {py_times[-1]:7.2f} {txt}"
                with open(output_file, 'a') as f:
                    f.write(f"{py_info}\n")
                print(py_info)
            
def do_test(input_device_keywords, wav_range = None):
    global t_start, py_cycle, baseline_counts, py_times
    py_cycle = ['', 0]

    with open(output_file,'w') as f:
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

    py_times = []
    
    wav_files = []
    if wav_range:
        for idx in range(*wav_range):
            wav_files.append(f"{wav_folder}/test_{idx:02d}.wav")

    rx = Receiver(ports = {'listen':None, 'send':2121}, input_keywords = input_device_keywords, latest_decode = 6)
    threading.Thread(target = monitor_decodes, daemon = True).start()
    soundout = SoundcardOut("CABLE, Input", wav_files)

    wav_file_time_offset = -1
    t = (wav_file_time_offset - time.time()) %15
    print(f"Waiting to play first wav file {t:6.2f}s")
    time.sleep(t)
    t_start = 15 * int(0.5 + time.time() / 15)
    soundout.start_wavs()

wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"
baseline_file = 'PyFT8m_baseline.txt'
output_file = 'PyFT8m.txt'

do_test("CABLE, Output", [8,28])
