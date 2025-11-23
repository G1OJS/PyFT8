import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
import numpy as np

class Waterfall:
    def __init__(self, spectrum):
        """
        Main FT8 waterfall display with candidate zooms and optional overlays.
        """
        self.spectrum = spectrum
        self.fine_grid_complex = spectrum.fine_grid_complex
        self.hops_persymb = spectrum.hops_persymb
        self.fbins_pertone = spectrum.fbins_pertone
        self.plt = plt

        # Main figure
        self.fig, (self.ax_main) = plt.subplots(1,1,figsize=(10, 4))
        self.ax_main.set_title("FT8 Waterfall")
        self.ax_main.set_xlabel("Frequency (Hz)")
        self.ax_main.set_ylabel("Time (s)")
        self.extent_main = [0, spectrum.max_freq, 0,  spectrum.nHops_loaded /(spectrum.sigspec.symbols_persec * spectrum.hops_persymb) ]
        self.ax_main.set_xlim(self.extent_main[0],self.extent_main[1])
        self.ax_main.set_ylim(self.extent_main[2],self.extent_main[3])

        self.zoom_axes = []
        self._candidate_patches = []
        self.fig.tight_layout()
        plt.show(block=False)
        plt.pause(0.1)

    # ----------------------------------------------------------
    def update_main(self, candidates=None, cyclestart_str=None):
        """Refresh main waterfall and draw candidate rectangles."""
        vals = np.abs(self.fine_grid_complex[:self.spectrum.nHops_loaded,:])**2
        self.im = self.ax_main.imshow(  vals, origin="lower", aspect="auto", extent = self.extent_main, 
                                        cmap="inferno", interpolation="none", norm=LogNorm() )
        self.im.norm.vmin = self.im.norm.vmax/100000
        if(cyclestart_str):
            self.ax_main.set_title(f"FT8 Waterfall for {cyclestart_str}")
        [p.remove() for p in reversed(self._candidate_patches)]
        self._candidate_patches.clear()

        if candidates:
            for c in candidates:
                origin_img = (c.origin_physical[1] - self.spectrum.dt/2, c.origin_physical[0])
                rect = patches.Rectangle(origin_img, c.sigspec.bw_Hz, (c.sigspec.num_symbols-1) / c.sigspec.symbols_persec,
                  linewidth=1.2,edgecolor="lime", facecolor="none"
                )
                self.ax_main.add_patch(rect)
                self._candidate_patches.append(rect)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()  # <-- forces actual draw
        plt.pause(0.1)
        
    # ----------------------------------------------------------
    def show_zoom(self, candidates, llr_overlay=True, cols=3, phase = False):
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
            cspec = c.fine_grid_complex
            vals = np.angle(cspec) if phase else np.abs(cspec)**2
            im = ax.imshow( vals, origin="lower", aspect="auto", extent=[-0.5, vals.shape[1]-0.5, -0.5, vals.shape[0]-0.5],
                            cmap="twilight" if phase else "inferno",
                            interpolation='none' )
            if(not phase):
                vmax = np.max(vals)
                im.norm = LogNorm(vmin=vmax/100000, vmax=vmax)
            ax.set_title(f"{c.origin_physical[1]:.0f}Hz {c.origin_physical[0]:.2f}s {c.message}")
            ax.set_xlabel("freq bin index")
            ax.set_ylabel("hop index")

            costas_pairs = [((symb_idx  + offset) * self.hops_persymb, tone * self.fbins_pertone)
                        for offset in (0, 36, 72) # magic numbers; move to a 'costas object' per mode
                        for symb_idx, tone in enumerate(c.sigspec.costas)]
            for hop_idx, fbin_idx in costas_pairs:
                rect = patches.Rectangle(
                    (fbin_idx - 0.5, hop_idx - 1 ), self.fbins_pertone, 3,
                    edgecolor='lime', facecolor='none'
                )
                ax.add_patch(rect)

            from mpl_toolkits.axes_grid1.inset_locator import inset_axes
            if llr_overlay and c.llr is not None:
                llr = np.array(c.llr, dtype=np.float32)
                llr_img = llr.reshape(-1, 1)
                llr_ax = inset_axes(parent_axes=ax, width="5%", height="100%", borderpad=0)
                llr_ax.imshow(llr_img, origin="lower", aspect="auto", cmap="bwr")
                llr_ax.set_xticks([])
                llr_ax.set_yticks([])
                llr_ax.set_title("LLR", fontsize=8)

        for ax in axes[n:]:
            ax.axis("off")

        zoom_fig.tight_layout(h_pad=3)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events() 
        plt.pause(0.001)
