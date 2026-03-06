import numpy as np
import matplotlib.pyplot as plt
import time
import pickle
import threading
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.gui import Gui

class Wsjtx_all_tailer:
    
    def __init__(self, on_decode, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt", silent = True):
        self.all_file = all_file
        self.on_decode = on_decode
        self.silent = silent
        threading.Thread(target = self.run).start()

    def run(self):
        def follow():
            with open(self.all_file, "r") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    yield line.strip()
        for line in follow():
            ls = line.split()
            try:
                cs, freq, dt, snr = ls[0], int(ls[6]), float(ls[5]), int(ls[4])
                msg = f"{ls[7]} {ls[8]} {ls[9]}"
                td = f"{time.time() %60:4.1f}"
                self.on_decode({'cs':cs, 'decoder':'WSJTX', 'f':int(freq), 'msg':msg, 'dt':dt, 'snr':snr, 'td':td})
            except:
                if(not self.silent):
                    print(f"Wsjtx_tailer error in line '{line}'")


data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"

global decodes, py_times, ws_times, decodes
decodes, py_times, ws_times = [], [], []

def get_cumulative_from_text_files(i0, i1, postfix):
    times = []
    t = 0
    for idx in range(i0, i1):
        with open(f"{data_folder}/test_{idx:02d}{postfix}", "r") as f:
            t += 15
            for l in f.readlines():
                times.append(t)
    return times

def on_decode(c):
    global decodes, py_times
    gui.post_decode((c.h0_idx, c.f0_idx, c.msg, int(c.snr)))
    print(f"{c.cyclestart_str} {c.snr} {c.dt:4.1f} {c.fHz} ~ {c.msg}")
    decodes.append(c.msg)
    py_times.append(time.time() - t_start)

def batch_test(i0, i1):
    from matplotlib.animation import FuncAnimation
    global t_start, gui
    wav_files = []
    for idx in range(i0, i1):
        wav_files.append(f"{data_folder}/test_{idx:02d}.wav")
    audio_in = AudioIn(3100, wav_files)
    gui = Gui(audio_in.dBgrid_main, 4, 2, {'c':'xxx', 'g':''}, None, None)
    rx = Receiver(audio_in, [200, 3100], on_decode)
    audio_in.start_wav_load()
    t_start = time.time()
    with open('baseline.pkl', 'rb') as f:
        py_times_prev = pickle.load(f)
        avg_cycle = np.max(py_times_prev) / (i1 - i0)
    ws_times = get_cumulative_from_text_files(i0, i1, "_wsjtx_2.7.0_NORM.txt")
    fl_times = get_cumulative_from_text_files(i0, i1, "_ft8_lib.txt")
    fig, ax = gui.plt.subplots()
    ws_line = ax.plot(ws_times, np.array(range(len(ws_times))), label = 'WSJT-X', color = 'blue')[0]
    ft_line = ax.plot(fl_times, np.array(range(len(fl_times))), label = 'ft8_lib', color = 'orange')[0]
    py_line = ax.plot([], [], label = 'PyFT8', color = 'red')[0]
    pp_line = ax.plot(py_times_prev, np.array(range(len(py_times_prev))), label = 'PyFT8 baseline', color = 'darkgreen', alpha = 0.3)
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes")
    ax.set_xlim(0, np.max(ws_times))
    ax.set_ylim(0, len(ws_times))
    ax.legend()
        
    def anim(frame):
        py_line.set_data(py_times, np.array(range(len(py_times))))
        with open('baseline_new.pkl', 'wb') as f:
            pickle.dump(py_times, f)
        with open('batch_decodes.pkl', 'wb') as f:
            pickle.dump(decodes, f)
        return py_line,
    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    gui.plt.show()

def on_wsjtx_decode(dd):
    global ws_times
    ws_times.append(time.time() - t_start)

def live_test():
    from matplotlib.animation import FuncAnimation
    global t_start, gui
    audio_in = AudioIn(3100)
    gui = Gui(audio_in.dBgrid_main, 4, 2, {'c':'xxx', 'g':''}, None, None)
    rx = Receiver(audio_in, [200, 3100], on_decode)
    t_start = time.time()
    input_device_idx = audio_in.find_device(["Cable", "Out"])
    audio_in.start_streamed_audio(input_device_idx)
    wsjtx_all_tailer = Wsjtx_all_tailer(on_wsjtx_decode, silent = True)

    fig, ax = gui.plt.subplots()
    ws_line = ax.plot([], [], label = 'WSJT-X')[0]
    py_line = ax.plot([], [], label = 'PyFT8')[0]
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes")
    ax.legend()
        
    def anim(frame):
        n_wsj = len(ws_times)
        n_pyf = len(py_times)
        ws_line.set_data(ws_times, np.array(range(n_wsj)))
        py_line.set_data(py_times, np.array(range(n_pyf)))
        n_max = np.max([n_wsj, n_pyf])
        if(n_max):
            ax.set_ylim(0, n_max)
        if any(py_times):
            ax.set_xlim(0, np.max(py_times))
        return ws_line, py_line,
    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    gui.plt.show()

#live_test()

batch_test(1,39)




