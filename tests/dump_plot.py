import pickle
import numpy as np
import matplotlib.pyplot as plt
fig, axs = plt.subplots(2,2, figsize = (8,8))
dBrange = 40

with open('SV2BRA_I4WQH_JN54_before.pkl','rb') as f:
    dat = pickle.load(f)
origin, all_audio_spectrum, signal_grid, score = dat
print(origin['tsec'], origin['fHz'], score)
before_dB = 20*np.log10(signal_grid)
im = axs[0,0].imshow(before_dB, origin = 'lower', vmax = np.max(before_dB), vmin = np.max(before_dB) - dBrange)
axs[0,0].set_title('Received signal')

with open('SV2BRA_I4WQH_JN54_after.pkl','rb') as f:
    dat = pickle.load(f)
origin, all_audio_spectrum, signal_grid, score = dat
print(origin['tsec'], origin['fHz'], score)
after_dB = 20*np.log10(signal_grid)
im = axs[0,1].imshow(after_dB, origin = 'lower', vmax = np.max(after_dB), vmin = np.max(after_dB) - dBrange)
axs[0,1].set_title('After')

diff = before_dB - after_dB
im = axs[1,0].imshow(diff, origin = 'lower')
axs[1,0].set_title('diff')

plt.show()
