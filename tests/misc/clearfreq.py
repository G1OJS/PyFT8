

import matplotlib.pyplot as plt
import pickle
import numpy as np



from numpy.lib.stride_tricks import sliding_window_view

fig, axs = plt.subplots(ncols=1, nrows=2, figsize=(5.5, 3.5))

with open('tmp.pkl','rb') as f:
    data = pickle.load(f)

axs[0].set_position([0.1,0.6,0.8,0.4])
axs[0].imshow(data.T, aspect = 'auto')

axs[1].set_position([0.1,0.1,0.8,0.4])

win = 8

fbin_sum = np.sum(data, axis = 1)
f0_idx, fn_idx = int(500/3.125), int(2000/3.125)
idx = np.argmin(fbin_sum[f0_idx:fn_idx])
clearest_frequency = (f0_idx + idx) * 3.125
print(f0_idx + idx)

freq = range(len(fbin_sum))
axs[1].plot(freq, fbin_sum)


plt.show()

