import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm

class Waterfall:
    def __init__(self, specbuff, hops_persymb, fbins_pertone, costas, t0=0, t1=15, f0=100, f1=3500):
        self.f0, self.f1, self.t0, self.t1 = t0, t1, f0, f1
        self.costas = costas
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        self.specbuff = specbuff
        self.fig, self.ax = plt.subplots(figsize=(10, 3))
        dt = self.specbuff.length_secs / (self.specbuff.nHops - 1)
        df = self.specbuff.width_Hz / (self.specbuff.nFreqs - 1)
        self.extent = [self.specbuff.freqs[0] - 0.5 * df, self.specbuff.freqs[-1] - 0.5 * df,
                       self.specbuff.times[0] - 0.5 * dt,  self.specbuff.times[-1] - 0.5 * dt]
        self.im = self.ax.imshow(self.specbuff.power, aspect='auto',origin='lower',
                        extent=self.extent,cmap='inferno',interpolation='none', norm=LogNorm())
        self.ax.set_xlabel('Frequency (Hz)')
        self.ax.set_ylabel('Time (s)')
        self.ax.set_xlim(f0, f1)
        self.ax.set_ylim(t0, t1)
        self.candidate_plots=[]

    def update(self, title = "FT8 Waterfall", candidates = None, show_n_candidates = 0):
        self.im.set_data(np.abs(self.specbuff.complex))
        print(self.specbuff.complex.shape)
        self.im.autoscale()
        [p.remove() for p in reversed(self.ax.patches)]
        if(candidates):
            for i, c in enumerate(candidates):
                t0_c = self.specbuff.times[c.tbin_idx] 
                f0_c = self.specbuff.freqs[c.fbin_idx] 
                dt_c = self.specbuff.times[c.tbin_idx + self.hops_persymb * c.num_symbols] - t0_c
                df_c = self.specbuff.freqs[c.fbin_idx + self.fbins_pertone * c.tones_persymb] - f0_c
                rect = patches.Rectangle(  (f0_c, t0_c), df_c, dt_c,
                                            linewidth=2, edgecolor='w', facecolor='none')
                self.ax.add_patch(rect)
                if(i<show_n_candidates):
                    self.candidate_plots.append(self.show_zoom(c, t0_c, t0_c+dt_c, f0_c, f0_c+df_c))
                    
        self.ax.set_title(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.5)

    def show_zoom(self, c, t0, t1, f0, f1):
        fig, axs = plt.subplots(2,1,figsize=(2, 5))
        im = axs[0].imshow(self.specbuff.power, aspect='auto',origin='lower',
                        extent=self.extent,cmap='inferno',interpolation='none', norm=LogNorm())
        for symb_idx, tone_idx in enumerate(self.costas):
            for symb_copy_idx in [symb_idx, symb_idx+36, symb_idx+72]:
                t0_sync = self.specbuff.times[c.tbin_idx + symb_copy_idx * self.hops_persymb]
                f0_sync = self.specbuff.freqs[c.fbin_idx + tone_idx * self.fbins_pertone]
                dt_sync = self.hops_persymb * self.specbuff.length_secs  / self.specbuff.nHops
                df_sync = self.fbins_pertone * self.specbuff.width_Hz  / self.specbuff.nFreqs
                rect = patches.Rectangle((f0_sync, t0_sync),  df_sync, dt_sync, edgecolor='black', facecolor= 'none' )
                axs[0].add_patch(rect)
        axs[0].set_title(f"{f0:.1f}Hz")
        axs[0].set_xlim(f0, f1)
        axs[0].set_ylim(t0, t1)

        im2 = axs[1].imshow(c.power_grid, aspect='auto',origin='lower',
                        extent=[-0.5, -0.5 + c.tones_persymb, -0.5, -0.5 + c.num_symbols] ,cmap='inferno',interpolation='none', norm=LogNorm())

        plt.pause(0.5)
        return plt
