import pickle
import numpy as np
import matplotlib.pyplot as plt
fig, axs = plt.subplots(2,2, figsize = (8,8))
dBrange = 40

def plot_file(ax, filename):
    with open(filename,'rb') as f:
        dat = pickle.load(f)
    origin, signal_grid = dat
    print(origin['tsec'], origin['fHz'])
    dB = 20*np.log10(signal_grid)
    im = ax.imshow(dB, origin = 'lower', vmax = np.max(dB), vmin = np.max(dB) - dBrange)
    ax.set_title(filename)


#plot_file(axs[0,0], 'before_refine_origin.pkl')
#plot_file(axs[0,1], 'after_refine_origin.pkl')
plot_file(axs[1,0], 'before_subtract.pkl')
plot_file(axs[1,1], 'after_subtract.pkl')



#diff = before_dB - after_dB
#im = axs[1,0].imshow(diff, origin = 'lower')
#axs[1,0].set_title('diff')

plt.show()

#0.22 1263.375
#2.24 1267.8125 = success
#1.02 1268.125 = success?

#usy/test_08      14.074 Rx FT8    -13  0.9 1264 SV2BRA I4WQH JN54
#usy/test_08      14.074 Rx FT8    -23  1.6 1267 CQ OR7EG JO11
