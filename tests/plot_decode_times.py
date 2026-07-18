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

plot_from_file(ax, 'live_decode_times_PyFT8.pkl', 'PyFT8', 'limegreen')

plot_from_file(ax, 'live_decode_times_WSJTx_2.7.0_1_FAST.pkl', 'WSJT-x_2.7.0_FAST', 'grey')
plot_from_file(ax, 'live_decode_times_WSJTx_2.7.0_2_NORM.pkl', 'WSJT-x_2.7.0_NORM', 'purple')
plot_from_file(ax, 'live_decode_times_WSJTx_2.7.0_3_DEEP.pkl', 'WSJT-x_2.7.0_DEEP', 'black')
        
ax.set_xlabel("Time, seconds")
ax.set_ylabel("Cumulative decodes (unique per cycle)")
fig.suptitle("Cumulative decode count against time")
ax.legend()
plt.show()
