import numpy as np
import matplotlib.pyplot as plt
import time
import pickle
import threading
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.waterfall import Waterfall

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
results_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/results/ft8_lib_20m_busy"

global times, counts, ws_times
times, ws_times = [], []

def get_cumulative_from_text_files(i0, i1, postfix):
    times, counts = [], []
    t, count = 0, 0
    for idx in range(i0, i1):
        with open(f"{data_folder}/test_{idx:02d}{postfix}", "r") as f:
            t += 15
            for l in f.readlines():
                count += (1 if len(l) > 10 else 0)
            times.append(t)
            counts.append(count)
    return times, counts

def on_decode(dd):
    global times
    print(dd['msg'])
    times.append(time.time() - t_start)

def batch_test(i0, i1):
    from matplotlib.animation import FuncAnimation
    global t_start
    wav_files = []
    for idx in range(i0, i1):
        wav_files.append(f"{data_folder}/test_{idx:02d}.wav")
    audio_in = AudioIn(None, 3100, wav_files)
    waterfall = Waterfall(audio_in.dBgrid_main, 4, 2, lambda msg: print(msg))
    t_start = time.time()
    rx = Receiver(audio_in, [200, 3100], on_decode, waterfall)

    wst, wsc = get_cumulative_from_text_files(i0, i1, "_wsjtx_2.7.0_NORM.txt")
    flt, flc = get_cumulative_from_text_files(i0, i1, "_ft8_lib.txt")
    fig, ax = waterfall.plt.subplots()
    wsj = ax.plot(wst, wsc, label = 'WSJT-X')
    ftl = ax.plot(flt, flc, label = 'ft8_lib')
    pyf = ax.plot([], [], label = 'PyFT8')
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes")
    
    with open('baseline.pkl', 'rb') as f:
        t, c = pickle.load(f)
    pyf_prev = ax.plot(t, c, label = 'PyFT8 baseline')
    ax.legend()
        
    def anim(frame):
        pyf[0].set_data(times, counts)
        with open('baseline_new.pkl', 'wb') as f:
            pickle.dump((times, counts), f)
        return pyf,
    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    waterfall.plt.show()

def on_wsjtx_decode(dd):
    global ws_times
    ws_times.append(time.time() - t_start)

def live_test():
    from matplotlib.animation import FuncAnimation
    global t_start
    audio_in = AudioIn(["Mic", "CODEC"], 3100, None)
    waterfall = Waterfall(audio_in.dBgrid_main, 4, 2, lambda msg: print(msg))
    t_start = time.time()
    rx = Receiver(audio_in, [200, 3100], on_decode, waterfall)

    wsjtx_all_tailer = Wsjtx_all_tailer(on_wsjtx_decode, silent = True)

    fig, ax = waterfall.plt.subplots()
    wsj = ax.plot([], [], label = 'WSJT-X')
    pyf = ax.plot([], [], label = 'PyFT8')
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes")
    ax.legend()
        
    def anim(frame):
        n_wsj = len(ws_times)
        n_pyf = len(times)
        wsj[0].set_data(ws_times, np.array(range(n_wsj)))
        pyf[0].set_data(times, np.array(range(n_pyf)))
        n_max = np.max([n_wsj, n_pyf])
        if(n_max):
            ax.set_ylim(0, n_max)
        if any(times):
            ax.set_xlim(0, np.max(times))
        return wsj, pyf,
    ani = FuncAnimation(fig, anim, interval = 5000, frames=(100000), blit=False)
    waterfall.plt.show()

live_test()

#batch_test(1,39)




