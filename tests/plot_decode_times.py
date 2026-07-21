import numpy as np
import matplotlib.pyplot as plt
import pickle


def plot_from_file(ax, fname, label, color):
    print(fname)
    with open(fname, 'rb') as f:
        times = pickle.load(f)
        ax.plot(times, np.array(range(len(times))), label = label, color = color)

i0, i1 = 1, 39
    
fig, ax = plt.subplots(figsize = (9,9))

plot_from_file(ax, 'live_decode_times_PyFT8_4_8_28.pkl', 'PyFT8', 'limegreen')

plot_from_file(ax, 'live_decode_times_WSJTx_2_8_28_FAST.pkl', 'WSJT-x_2.7.0_FAST', 'black')
plot_from_file(ax, 'live_decode_times_WSJTx_5_8_28_FAST-AP.pkl', 'WSJT-x_2.7.0_FAST-AP', 'blue')

plot_from_file(ax, 'live_decode_times_WSJTx_3_8_28_DEEP.pkl', 'WSJT-x_2.7.0_DEEP', 'purple')
#plot_from_file(ax, 'live_decode_times_WSJTx_4_8_28_DEEP-AP.pkl', 'WSJT-x_2.7.0_DEEP-AP', 'red')
        
ax.set_xlabel("Time, seconds")
ax.set_ylabel("Cumulative decodes (unique per cycle)")
fig.suptitle("Cumulative decode count against time")
ax.legend()

from matplotlib.ticker import AutoMinorLocator, MultipleLocator
ax.xaxis.set_major_locator(MultipleLocator(15))
ax.xaxis.set_minor_locator(MultipleLocator(1))
plt.grid(which = 'major', axis = 'x')
plt.grid(which = 'major', axis = 'y')

plt.show()
