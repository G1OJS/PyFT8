
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class Waterfall:
    def __init__(self, wf, t0=0, t1=15, f0=100, f1=4000):
        self.fig, self.ax = plt.subplots(figsize=(10, 3))
        self.im = self.ax.imshow(wf.power ,aspect='auto',origin='lower',
                        extent=[wf.freqs[0], wf.freqs[-1], wf.times[0], wf.times[-1]],cmap='inferno',interpolation='none')
        self.ax.set_xlabel('Frequency (Hz)')
        self.ax.set_ylabel('Time (s)')
        self.ax.set_title('FT8 waterfall')
        self.ax.set_xlim(f0, f1)
        self.ax.set_ylim(t0, t1)
        #plt.pause(0.5)

    def update(self, wf, title = "FT8 Waterfall", candidates = None):
        self.im.set_data(wf.power)
        self.im.autoscale()
        [p.remove() for p in reversed(self.ax.patches)]
        if(candidates):
            for c in candidates:
                rect = patches.Rectangle((c.freq-0.5*c.hz_pertone, c.dt-0.5*c.symbol_secs), 8*c.hz_pertone, c.num_symbols * c.symbol_secs, linewidth=1, edgecolor='r', facecolor='none')
                self.ax.add_patch(rect)
        self.ax.set_title(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.5)

def show_candidate(wf, candidate):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    t0_idx = candidate.tbin_idx
    f0_idx = candidate.fbin_idx
    t1_idx = t0_idx + modulation['num_symbols'] * demod_params['hops_persymb']
    f1_idx = f0_idx + 8 * demod_params['fbins_per_tone']
    cwf = wf.dB[t0_idx:t1_idx, f0_idx:f1_idx]
    fig, ax = plt.subplots(figsize=(5, 10))
    ax.imshow(cwf,aspect='auto',origin='lower',cmap='inferno',interpolation='none')
    for i, tone in enumerate(modulation['costas']):
        for j in [0,36,72]:
            rect = patches.Rectangle((tone-0.5, (i+j-0.5)*demod_params['hops_persymb']),
                                     1, demod_params['hops_persymb'], linewidth=2, facecolor='none',
                                     edgecolor='black' )
            ax.add_patch(rect)
    ax.set_xlabel('Tone')
    ax.set_ylabel('Hop')
    ax.set_title('FT8 candidate')

    plt.show()
