import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator
import pickle


def plot_from_file(ax, fname, label, color):
    print(fname)
    with open(fname, 'rb') as f:
        times = pickle.load(f)
        ax.plot(times, np.array(range(len(times))), label = label, color = color, marker = 'o', markersize = 3)

fig, ax = plt.subplots(figsize = (9,9))
ax.yaxis.set_label_position("right")


plot_from_file(ax, 'live_decode_times_PyFT8.pkl', 'PyFT8', 'limegreen')
plot_from_file(ax, 'live_decode_times_PyFT8_8_28_baseline.pkl', 'PyFT8', 'orange')
plot_from_file(ax, 'live_decode_times_WSJTx_8_28_FAST.pkl', 'WSJT-x_2.7.0_FAST', 'black')

ax.legend()
        
ax.set_xlabel("Time, seconds")
ax.set_ylabel("Cumulative decodes (unique per cycle)")
fig.suptitle("Cumulative decode count against time\nPyFT8 vs WSJT-x v2.7.0")
ax.legend()

from matplotlib.ticker import AutoMinorLocator, MultipleLocator
ax.xaxis.set_major_locator(MultipleLocator(15))
ax.xaxis.set_minor_locator(MultipleLocator(1))
ax.yaxis.set_major_locator(MultipleLocator(100))
ax.yaxis.set_minor_locator(MultipleLocator(25))
plt.grid(which = 'major', axis = 'x')
plt.grid(which = 'major', axis = 'y')
ax.yaxis.tick_right()

plt.show()
