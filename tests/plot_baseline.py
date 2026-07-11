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
            t += avg_cycle # approximate until real times folded in
            for l in f.readlines():
                times.append(t)
    return times

avg_cycle = 15.1

ws_times = get_cumulative_from_text_files(i0, i1, "_wsjtx_2.7.0_NORM.txt")
fl_times = get_cumulative_from_text_files(i0, i1, "_ft8_lib.txt")
    
fig, ax = plt.subplots()
ws_line = ax.plot(ws_times, np.array(range(len(ws_times))), label = 'WSJT-X', color = 'gray')[0]
ft_line = ax.plot(fl_times, np.array(range(len(fl_times))), label = 'ft8_lib', color = 'lightgreen')[0]



for filename in ['baseline - min_search_start=11.5.pkl', 'baseline - min_search_start=12.pkl', 'baseline - min_search_start=13.pkl']:
    with open(filename, 'rb') as f:
        py_times = pickle.load(f)
        ax.plot(py_times, np.array(range(len(py_times))), label = 'PyFT8 ' + filename)
        
ax.set_xlabel("Time, seconds")
ax.set_ylabel("Cumulative decodes (unique per cycle)")
fig.suptitle("Cumulative decode count against time")
ax.set_xlim(0, np.max(ws_times) + 15)
ax.set_ylim(0, len(ws_times))
ax.legend()
plt.show()
