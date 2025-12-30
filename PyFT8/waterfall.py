import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
import numpy as np

class Waterfall:
    def __init__(self, spectrum):

        self.spectrum = spectrum
        self.plt = plt

        self.fig, (self.ax_main) = plt.subplots(1,1,figsize=(10, 4))
        self.ax_main.set_title("FT8 Waterfall")
        self.ax_main.set_xlabel("Frequency bin")
        self.ax_main.set_ylabel("Time bin")
        self.extent_main = [-0.5, spectrum.nFreqs - 1 -0.5, -0.5,  spectrum.hops_percycle -1 -0.5]

        self.zoom_axes = []
        self._candidate_patches = []
        self.fig.tight_layout()
        plt.show(block=False)
        plt.pause(0.1)

    # ----------------------------------------------------------
    def update_main(self, candidates=None, cyclestart_str=None):

        self.im = self.ax_main.imshow(self.spectrum.pgrid_fine, origin="lower", aspect="auto", 
                                        cmap="inferno", interpolation="none", norm=LogNorm() )
        self.im.norm.vmin = self.im.norm.vmax/100000
        if(cyclestart_str):
            self.ax_main.set_title(f"FT8 Waterfall for {cyclestart_str}")
        [p.remove() for p in reversed(self._candidate_patches)]
        self._candidate_patches.clear()
        
        cands_for_plot = candidates.copy()
        def candsort(c):
            if(c.msg): return 1
            return 0
        cands_for_plot.sort(key = lambda c: candsort(c))
        if candidates:
            for c in cands_for_plot:
                origin_img = (c.f0_idx, c.h0_idx)
                cand_color = "lightgrey"
                if(c.msg): cand_color = "lime"
                rect = patches.Rectangle(origin_img, self.spectrum.sigspec.tones_persymb * self.spectrum.fbins_pertone,
                                         self.spectrum.sigspec.num_symbols * self.spectrum.hops_persymb,
                  linewidth=1.2,edgecolor=cand_color, facecolor="none"
                )
                self.ax_main.add_patch(rect)
                self._candidate_patches.append(rect)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()  
        plt.pause(0.1)
        

    def show_zoom(self, candidates, cols=3):
        """
        Create per-candidate zoom boxes.
        Optionally overlay LLRs if candidate.llr is present.
        """
        n = len(candidates)
        if (n==0): return
        rows = int(np.ceil(n / cols))
        zoom_fig, axes = plt.subplots(rows, cols, figsize=(3.5 * cols, 5 * rows))
        axes = np.atleast_1d(axes).flatten()
        self.zoom_axes = axes

        for i, c in enumerate(candidates):
            ax = axes[i]
            f0_idx = c.f0_idx
            h0_idx = c.h0_idx
            vals =self.spectrum.pgrid_fine[h0_idx:h0_idx + self.spectrum.sigspec.num_symbols * self.spectrum.hops_persymb,
                                        f0_idx:f0_idx + self.spectrum.sigspec.tones_persymb * self.spectrum.fbins_pertone]

            im = ax.imshow( vals, origin="lower", aspect="auto", extent=[-0.5, vals.shape[1]-0.5, -0.5, vals.shape[0]-0.5],
                            cmap="inferno",  interpolation='none' )
            vmax = np.max(vals)
            im.norm = LogNorm(vmin=vmax/100000, vmax=vmax)
            ax.set_title(f"{c.fHz:.0f}Hz {c.dt:.2f}s {c.call_b}")
            ax.set_xlabel("freq bin index")
            ax.set_ylabel("hop index")

            costas_pairs = [((symb_idx  + offset) * self.spectrum.hops_persymb, tone * self.spectrum.fbins_pertone)
                        for offset in (0, 36, 72) # magic numbers; move to a 'costas object' per mode
                        for symb_idx, tone in enumerate(self.spectrum.sigspec.costas)]
            for hop_idx, fbin_idx in costas_pairs:
                rect = patches.Rectangle(
                    (fbin_idx, hop_idx - 0.5 ), self.spectrum.fbins_pertone, 1,
                    edgecolor='lime', facecolor='none'
                )
                ax.add_patch(rect)

        for ax in axes[n:]:
            ax.axis("off")

        zoom_fig.tight_layout(h_pad=3)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events() 
        plt.pause(0.001)
