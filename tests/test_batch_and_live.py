import numpy as np
import matplotlib.pyplot as plt
import pickle, threading
from matplotlib.animation import FuncAnimation
from PyFT8.time_utils import time_utils
from PyFT8.receiver import Receiver
from PyFT8.gui import Gui

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
    grid_ptr = rx.audio_in.search_grid_ptr
    decode_time_from_grid = 30* grid_ptr / rx.audio_in.search_hops_per_grid
    print(f"{len(py_times):03d}: {' '.join(c.msg_tuple):30s} demap_start: {c.demap_started:5.1f} " +
          f"decoded at: {decode_time_from_grid:6.2f}s h0: {c.origin['h0_idx']:3d} " +
          f"Sync score: {c.origin['score']:3.0f}  n_sync_matches: {c.n_sync_matches:2d} LLR_SD: {c.llr_sd:5.1f} Pass: {c.ipass:2d} n_its: {c.n_its:3d} ")
    if c.msg_tuple is not None:
        py_times.append(time_utils.time() - t_start)

def on_wsjtx_decode(dd):
    global ws_times, both_started
    if not both_started:
        if len(py_times):
            ws_times = [wt for wt in ws_times if py_times[0]-wt < 5]
            both_started = True
    ws_times.append(time_utils.time() - t_start)

def test_common(input_source):
    global gui, rx, t_start
    global decodes, py_times, ws_times, decodes
    global fig, ax
    decodes, py_times, ws_times = [], [], []
    using_wav_files = input_source[0].endswith('.wav')
    input_device_keywords = input_source if not using_wav_files else None
    wav_files = input_source if using_wav_files else None
    rx = Receiver([100, 3000], input_device_keywords, wav_files = wav_files, on_decode = on_decode,
                sync_score_min = 85, max_cands = 1000, main_demap_start = 13) # now demap not search, so add a second on to this (14) and rebaseline
    #gui = Gui(rx, {'bands':{'20m':14.074},'station':{'call':'G1OJS','grid':'IO90'}}, None, None, None)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10,10))
    t_start = time_utils.time()

def batch_test(i0, i1):
    wav_files = []
    for idx in range(i0, i1):
        wav_files.append(f"{wav_folder}/test_{idx:02d}.wav")
    test_common(wav_files)
    t_start = time_utils.time()
    with open('baseline.pkl', 'rb') as f:
        py_times_prev = pickle.load(f)
        avg_cycle = np.max(py_times_prev) / (i1 - i0)
    ws_times = get_cumulative_from_text_files(i0, i1, "_wsjtx_2.7.0_NORM.txt")
    fl_times = get_cumulative_from_text_files(i0, i1, "_ft8_lib.txt")
    ws_line = ax.plot(ws_times, np.array(range(len(ws_times))), label = 'WSJT-X', color = 'blue')[0]
    ft_line = ax.plot(fl_times, np.array(range(len(fl_times))), label = 'ft8_lib', color = 'orange')[0]
    py_line = ax.plot([], [], label = 'PyFT8', color = 'red')[0]
    pp_line = ax.plot(py_times_prev, np.array(range(len(py_times_prev))), label = 'PyFT8 baseline', color = 'darkgreen', alpha = 0.3)
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes") 
    ax.set_xlim(0, ws_times[-1] + 10)
    ax.set_ylim(0, len(ws_times) + 10)
    ax.legend()
 
    def anim(frame):
        py_line.set_data(py_times, np.array(range(len(py_times))))
        with open('baseline_new.pkl', 'wb') as f:
            pickle.dump(py_times, f)
        return py_line,
    
    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    plt.show()


def live_test():
    global both_started
    both_started = False
    test_common(["Mic", "CODEC"])
    wsjtx_all_tailer = Wsjtx_all_tailer(on_wsjtx_decode, silent = True)
    
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
    plt.show()

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"

gui = None

#live_test()
batch_test(1,39)




