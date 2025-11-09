import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
import numpy as np

class Waterfall:
    def __init__(self, spectrum, t0=0, t1=None, f0=100, f1=None):
        """
        Main FT8 waterfall display with candidate zooms and optional overlays.
        """
        self.spectrum = spectrum
        self.costas = spectrum.sigspec.costas
        self.hops_persymb = spectrum.hops_persymb
        self.fbins_pertone = spectrum.fbins_pertone
        self.t0, self.t1 = t0, t1 or spectrum.sigspec.frame_secs
        self.f0, self.f1 = f0, f1 or (spectrum.sample_rate / 2)
        self.dt = spectrum.dt
        self.df = spectrum.df
        self.extent = spectrum.bounds.extent

        # Main figure
        self.fig, (self.ax_main) = plt.subplots(1,1,figsize=(10, 4))
        self.im = self.ax_main.imshow(
            np.abs(spectrum.complex)+0.1,
            origin="lower",
            aspect="auto",
            extent=self.extent,
            cmap="inferno",
            interpolation="none",
            norm=LogNorm()
        )
        self.ax_main.set_title("FT8 Waterfall")
        self.ax_main.set_xlabel("Frequency (Hz)")
        self.ax_main.set_ylabel("Time (s)")
        self.ax_main.set_xlim(self.f0, self.f1)
        self.ax_main.set_ylim(self.t0, self.t1)

        self.zoom_axes = []
        self._candidate_patches = []
        self.fig.tight_layout()
        plt.show(block=False)
        plt.pause(0.1)

    # ----------------------------------------------------------
    def update_main(self, candidates=None, cyclestart_str=None):
        """Refresh main waterfall and draw candidate rectangles."""
        self.im.set_data(np.abs(self.spectrum.complex)+0.1)
        self.im.autoscale()
        self.im.norm.vmin = self.im.norm.vmax/1000000
        if(cyclestart_str):
            self.ax_main.set_title(f"FT8 Waterfall for {cyclestart_str}")
        [p.remove() for p in reversed(self._candidate_patches)]
        self._candidate_patches.clear()

        if candidates:
            for c in candidates:
                rect = patches.Rectangle( (c.bounds.f0, c.bounds.t0),
                  c.bounds.fn - c.bounds.f0,c.bounds.tn - c.bounds.t0,
                  linewidth=1.2,edgecolor="lime", facecolor="none"
                )
                self.ax_main.add_patch(rect)
                self._candidate_patches.append(rect)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()  # <-- forces actual draw
        plt.pause(0.1)

    # ----------------------------------------------------------
    def show_decodes(self, decodes):
        """Update the text panel with latest decode messages."""
        self.textaxis.axis('off')
        self.textaxis.clear()
        self.textaxis.text(0, 1, "\n".join(decodes),
                               va='top', family='monospace', fontsize=9)
        self.fig.canvas.draw()
        self.textaxis.axis('off')
        self.fig.canvas.flush_events()
        self.textaxis.axis('off')
        
    # ----------------------------------------------------------
    def show_zoom(self, candidates, llr_overlay=True, cols=3, phase = False):
        """
        Create per-candidate zoom boxes (gridded subplots).
        Optionally overlay LLRs if candidate.llr is present.
        """
        candidates_with_decodes = []
        for i, c in enumerate(candidates):
            if c.message:
                candidates_with_decodes.append(c)
        
        n = len(candidates_with_decodes)
        if (n==0): return
        rows = int(np.ceil(n / cols))
        zoom_fig, axes = plt.subplots(rows, cols, figsize=(3.5 * cols, 5 * rows))
        axes = np.atleast_1d(axes).flatten()
        self.zoom_axes = axes

        # Precompute Costas skeleton (symbol, tone index pairs)
        costas_pairs = [((symb_idx  + offset) * self.hops_persymb, tone * self.fbins_pertone)
                        for offset in (0, 36, 72) # magic numbers; move to a 'costas object' per mode
                        for symb_idx, tone in enumerate(self.costas)]

        
        for i, c in enumerate(candidates_with_decodes):
            ax = axes[i]
            pwr = c.phase_grid if phase else (c.power_grid +0.1)
            im = ax.imshow(
                pwr,
                origin="lower",
                aspect="auto",
                cmap="twilight" if phase else "inferno",
                interpolation='none'
            )
            if(not phase): im.norm = LogNorm()
            ax.set_title(f"{c.bounds.f0:.0f}Hz {c.bounds.t0:.2f}s {c.message}")
            ax.set_xlabel("freq bin index")
            ax.set_ylabel("hop index")

            # --- Costas rectangles ---
            for symb_idx, tone_idx in costas_pairs:
                rect = patches.Rectangle(
                    (tone_idx - 0.5, symb_idx - 0.5), self.fbins_pertone, self.hops_persymb,
                    edgecolor='lime', facecolor='none', linewidth=1.2
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
        self.fig.canvas.flush_events()  # <-- forces actual draw
        plt.pause(0.001)
