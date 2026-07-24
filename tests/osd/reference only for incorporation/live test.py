import numpy as np
import matplotlib.pyplot as plt
import pickle, threading, pyaudio, sys
from PyFT8.time_utils import time_utils
from matplotlib.animation import FuncAnimation
from PyFT8.time_utils import time_utils
from PyFT8.receiver import Receiver
from PyFT8.transmitter import SoundcardOut
from PyFT8.gui import Gui

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
        import wave
        t = (self.wav_file_time_offset - time_utils.cycle_time()) %15
        time_utils.sleep(t)
        dt = 0.6/4
        for i, w in enumerate(wav_files):
            print(f"File {i}")
            wv = wave.open(w, 'rb')
            audio_bytes = wv.readframes(sr*16)
            audio_bytes = audio_bytes[-int(sr*(15-dt))*2:]

            stream = self.pya.open(format=pyaudio.paInt16, channels=1, rate = sr, output=True,
                              output_device_index = self.output_device_index)
            stream.write(audio_bytes)
            stream.stop_stream()
            stream.close()

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
            try:
                cs, freq, dt, snr = ls[0], int(ls[6]), float(ls[5]), int(ls[4])
                msg = f"{ls[7]} {ls[8]} {ls[9]}"
                td = f"{time_utils.time() %60:4.1f}"
                self.on_decode({'cs':cs, 'decoder':'WSJTX', 'origin':{'f0':int(freq), 't0':dt, 'score':0}, 'msg':msg, 'snr':snr, 'td':td})
            except:
                if(not self.silent):
                    print(f"Wsjtx_tailer error in line '{line}'")

timerange = [15, -15]
freqrange = [4000, 0]
def process_message(m):
    global timerange, freqrange
    py_times.append(m['decode_completed'] - t_start)
    tsec = m['tsec']
    if tsec < timerange[0]: timerange[0] = tsec
    if tsec > timerange[1]: timerange[1] = tsec
    fHz = m['fHz'] 
    if fHz < freqrange[0]: freqrange[0] = fHz
    if fHz > freqrange[1]: freqrange[1] = fHz
    print(f"{m['decode_status']:35s} t {timerange[0]:+05.2f},{timerange[1]:+05.2f} f {freqrange[0]:04.0f},{freqrange[1]:04.0f} {m['all_txt_format']}")

def on_wsjtx_decode(dd):
    global ws_times, both_started
    if not both_started:
        if len(py_times):
            ws_times = [wt for wt in ws_times if py_times[0]-wt < 5]
            both_started = True
    ws_times.append(time_utils.time() - t_start)



def do_test(input_device_keywords, wav_range = None):
    global both_started
    global gui, rx, t_start, comms_hub
    global decodes, py_times, ws_times, decodes
    global fig, ax
    from matplotlib.ticker import AutoMinorLocator, MultipleLocator
    
    fig, ax = plt.subplots(figsize=(10,10))
    ws_line = ax.plot([], [], label = 'WSJT-X', marker = 'o', markersize = 3)[0]
    py_line = ax.plot([], [], label = 'PyFT8', marker = 'o', markersize = 3)[0]
    baseline = ax.plot([], [], label = 'PyFT8 - baseline', marker = 'o', markersize = 3)[0]
    with open('live_decode_times_PyFT8_8_28_baseline.pkl', 'rb') as f:
        baseline_times = pickle.load(f)
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes")
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    ax.yaxis.set_major_locator(MultipleLocator(100))
    ax.yaxis.set_minor_locator(MultipleLocator(25))
    ax.legend()
    ax.xaxis.set_major_locator(MultipleLocator(15))
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    plt.grid(which = 'major', axis = 'x')

    wav_files = []
    if wav_range:
        for idx in range(*wav_range):
            wav_files.append(f"{wav_folder}/test_{idx:02d}.wav")

    wsjtx_all_tailer = Wsjtx_all_tailer(on_wsjtx_decode, silent = True)

    t = 15-time_utils.cycle_time()
    if t > 0.05:
        print(f"Waiting to start test on next cycle ({t:6.1f}s)")
        time_utils.sleep(t)
    t_start = time_utils.time()

    if wav_files:
       soundout = SoundcardOut("CABLE, Input", wav_files, wav_file_time_offset = -1)

    both_started = True
    decodes, py_times, ws_times = [], [], []
    
    receiver = Receiver(input_device_keywords, process_message, sync_score_min = 85, max_cands = 200,
                  search_freq_range = [200, 2800], search_timerange = [-2.5, 3.5])
    if not receiver.audio_in.input_device_idx:
        time_utils.tlog(f"[Audio] No input audio device found matching {input_device_keywords}", verbose = True)
        sys.exit(1)
 
    def anim(frame):
        n_wsj = len(ws_times)
        n_pyf = len(py_times)
        n_baseline = len(baseline_times)
        ws_line.set_data(ws_times, np.array(range(n_wsj)))
        py_line.set_data(py_times, np.array(range(n_pyf)))
        baseline.set_data(baseline_times, np.array(range(n_baseline)))
        n_max = np.max([n_wsj, n_pyf, n_baseline])
        if(n_max):
            ax.set_ylim(0, n_max+20)
        if any(py_times):
            ax.set_xlim(0, np.max(py_times)+20)
            with open('live_decode_times_PyFT8.pkl', 'wb') as f:
                pickle.dump(py_times, f)
            with open('live_decode_times_WSJTx.pkl', 'wb') as f:
                pickle.dump(ws_times, f)

    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    plt.show()

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"

#do_test("Mic, CODEC")
do_test("CABLE, Output", [8,28])





