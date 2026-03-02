import numpy as np
import matplotlib.pyplot as plt
import time
import pickle
import threading
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.waterfall import Waterfall
from PyFT8.utilities import tprint

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
results_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/results/ft8_lib_20m_busy"

global decodes, times, counts
decodes, times, counts = [], [], []

def analyse_cumulative(i0, i1, postfix):
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
    global decodes, times, counts
    decodes.append(dd)
    nc, msg = len(decodes), dd['msg']
    tprint(f"{nc:04d} {msg}")
    times.append(time.time() - t_start)
    counts.append(nc)

def run_test(i0, i1):
    from matplotlib.animation import FuncAnimation
    global t_start
    tprint("Start test")
    wav_files = []
    for idx in range(i0, i1):
        wav_files.append(f"{data_folder}/test_{idx:02d}.wav")
    audio_in = AudioIn(None, 3100, wav_files)
    waterfall = Waterfall(audio_in.dBgrid_main, 4, 2, lambda msg: print(msg))
    t_start = time.time()
    rx = Receiver(audio_in, [200, 3100], on_decode, waterfall)

    wst, wsc = analyse_cumulative(i0, i1, "_wsjtx_2.7.0_NORM.txt")
    flt, flc = analyse_cumulative(i0, i1, "_ft8_lib.txt")
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


run_test(1,39)




