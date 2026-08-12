import numpy as np
import matplotlib.pyplot as plt
import pickle

SAMP_RATE = 12000
SYM_RATE = 6.25

def plot_grid(ax, audio_buffer, frng, title):
    hps, bpt = 1, 1
    hpc = int(hps * SYM_RATE * 15)
    grid_fft_len = int(bpt * SAMP_RATE / SYM_RATE)
    samps_per_hop = int(SAMP_RATE / (SYM_RATE * hps) )
    grid = np.zeros((hpc, grid_fft_len))
    df = SAMP_RATE / grid_fft_len
    h0 = int(grid_fft_len / samps_per_hop)
    fft_in = np.zeros(grid_fft_len)
    search_fft_window = np.hanning(grid_fft_len).astype(np.float32)
    for h in range(1, hpc):
        sn = h * samps_per_hop
        sn = sn if sn < len(audio_buffer) else len(audio_buffer)
        s0 = sn - grid_fft_len
        s0 = s0 if s0 > 0 else 0
        fft_in [:sn-s0] = audio_buffer[s0: sn]
        grid[h,:] = np.abs(np.fft.fft(fft_in * search_fft_window))
    dB_grid = 20.0*np.log10(grid + 1e-12)
    if0 = int(frng[0] / df)
    if1 = int(frng[1] / df)
    vals = dB_grid[:, if0:if1]
    trng = len(audio_buffer) / SAMP_RATE
    im1 = ax.imshow(vals, vmax = 90, vmin = 50, origin = 'lower',
                    extent = [frng[0], frng[1], 0, trng], aspect = 'auto')
    ax.set_title(f"{title} max = {np.max(vals):6.1f}")
    return grid

def plot_two(frng = [200, 2800]):
    frng[0] = frng[0] if frng[0] >= 0 else 0
    fig, axs = plt.subplots(2,1, figsize = (5,10))
    plot_grid(axs[0], ex, frng, "Received")
    plot_grid(axs[1], ex - sub, frng, 'Result')
    for ax in axs[:-1]:
        ax.set_xticks([])
    fig.suptitle(f"{origin['fHz']:6.2f}Hz {origin['tsec']:6.2f}s")
    plt.show()
    
def plot_all_freqdomain(frng = [200, 2800]):
    frng[0] = frng[0] if frng[0] >= 0 else 0
    fig, axs = plt.subplots(5,1, figsize = (5,10))
    grid_both = plot_grid(axs[0], ex, frng, "Received")
    grid_gen = plot_grid(axs[1], 100*np.real(sig_audio), frng,'Generated')
    plot_grid(axs[2], np.real(amp), [0,500], 'Re(Camp)')
    plot_grid(axs[3], sub, frng, '2*Re(Camp * Received)')
    grid_res = plot_grid(axs[4], ex - sub, frng, 'Result')
    plot_grid(axs[4], ex - sub, frng, 'Result')
    for ax in axs[:-1]:
        ax.set_xticks([])
    plt.show()


import os
path = './'
for fnm in os.listdir(path):
    if fnm.endswith('pkl'):
        print(fnm)
        with open(path + fnm, 'rb') as f:
            ex, sig_audio, amp, sub, origin, symbols = pickle.load(f)
        fHz = origin['fHz']
        tsec = origin['tsec']
        plot_two()
        #plot_all_freqdomain(frng = [fHz - 50, fHz + 150])
        #plot_all_freqdomain()
