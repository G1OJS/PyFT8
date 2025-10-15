
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class Waterfall:
    def __init__(self, wf, t0=0, t1=15, f0=100, f1=3500):
        self.fig, self.ax = plt.subplots(figsize=(10, 3))
        self.im = self.ax.imshow(wf.power ,aspect='auto',origin='lower',
                        extent=[wf.freqs[0], wf.freqs[-1], wf.times[0], wf.times[-1]],cmap='inferno',interpolation='none')
        self.ax.set_xlabel('Frequency (Hz)')
        self.ax.set_ylabel('Time (s)')
        self.ax.set_title('FT8 waterfall')
        self.ax.set_xlim(f0, f1)
        self.ax.set_ylim(t0, t1)
        self.candidate_plots=[]
        #plt.pause(0.5)

    def update(self, wf, title = "FT8 Waterfall", candidates = None):
        self.im.set_data(wf.power)
        self.im.autoscale()
        [p.remove() for p in reversed(self.ax.patches)]
        if(candidates):
            for i, c in enumerate(candidates):
                rect = patches.Rectangle((c.freq-0.5*c.hz_pertone, c.dt-0.5*c.symbol_secs), 8*c.hz_pertone, c.num_symbols * c.symbol_secs, linewidth=2, edgecolor='w', facecolor='none')
                self.ax.add_patch(rect)
               # if(i==0): self.candidate_plots.append(show_candidate(wf,c))
        self.ax.set_title(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.5)
      #  for f in self.candidate_plots:
         #   plt.close(f)

def show_candidate(wf, candidate):
    costas = [3, 1, 4, 0, 6, 5, 2]
    t0_idx = candidate.tbin_idx
    f0_idx = candidate.fbin_idx
    t1_idx = t0_idx + candidate.num_symbols * candidate.hops_persymb
    f1_idx = f0_idx + 8 * candidate.fbins_pertone
    cwf = wf.dB[t0_idx:t1_idx, f0_idx:f1_idx]
    fig, ax = plt.subplots(figsize=(5, 10))
    ax.imshow(cwf,aspect='auto',origin='lower',cmap='inferno',interpolation='none')
    for i, tone in enumerate(costas):
        for j in [0,36,72]:
            rect = patches.Rectangle((tone-0.5, (i+j-0.5)*candidate.hops_persymb),
                                     1, candidate.hops_persymb, linewidth=2, facecolor='none',
                                     edgecolor='black' )
            ax.add_patch(rect)
    ax.set_xlabel('Tone')
    ax.set_ylabel('Hop')
    ax.set_title('FT8 candidate')
    plt.pause(0.1)
    return fig
