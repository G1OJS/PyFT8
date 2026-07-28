import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator


def plot_from_file(ax, fname, label, color):
    print(fname)
    with open(fname, 'r') as f:
        lines = f.readlines()
        times = [float(l.split()[2]) for l in lines]
        ax.plot(times, np.array(range(len(times))), label = label, color = color, marker = 'o', markersize = 3)

fig, ax = plt.subplots(figsize = (9,9))
ax.yaxis.set_label_position("right")


plot_from_file(ax, 'PyFT8_8_28_baseline.txt', 'PyFT8-baseline', 'green')
plot_from_file(ax, 'PyFT8_8_28.txt', 'PyFT8', 'orange')
plot_from_file(ax, 'WSJTx_8_28_FAST.txt', 'WSJT-x_2.7.0_FAST', 'blue')

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
