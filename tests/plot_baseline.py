import numpy as np
import matplotlib.pyplot as plt
import pickle

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"

i0, i1 = 1, 39

def get_cumulative_from_text_files(i0, i1, postfix):
    times = []
    t = 0
    for idx in range(i0, i1):
        with open(f"{data_folder}/test_{idx:02d}{postfix}", "r") as f:
            t += 15
            for l in f.readlines():
                times.append(t)
    return times

ws_times = get_cumulative_from_text_files(i0, i1, "_wsjtx_2.7.0_NORM.txt")
fl_times = get_cumulative_from_text_files(i0, i1, "_ft8_lib.txt")
    
fig, ax = plt.subplots()
with open('baseline.pkl', 'rb') as f:
    py_times_prev = pickle.load(f)
ws_line = ax.plot(ws_times, np.array(range(len(ws_times))), label = 'WSJT-X', color = 'blue')[0]
ft_line = ax.plot(fl_times, np.array(range(len(fl_times))), label = 'ft8_lib', color = 'red')[0]
pp_line = ax.plot(py_times_prev, np.array(range(len(py_times_prev))), label = 'PyFT8', color = 'darkgreen')
ax.set_xlabel("Time, seconds")
ax.set_ylabel("Cumulative decodes")
ax.set_xlim(0, np.max(ws_times))
ax.set_ylim(0, len(ws_times))
ax.legend()
plt.show()
