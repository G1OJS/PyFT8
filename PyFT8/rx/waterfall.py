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
        self.fig, (self.ax_main, self.textaxis) = plt.subplots(2,1,figsize=(10, 4))
        self.textaxis.axis('off')
        self.im = self.ax_main.imshow(
            spectrum.power,
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
        self.im.set_data(self.spectrum.power)
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
        lines = [d['msg'] for d in decodes]
        self.textaxis.text(0, 1, "\n".join(lines),
                               va='top', family='monospace', fontsize=9)
        self.fig.canvas.draw()
        self.textaxis.axis('off')
        self.fig.canvas.flush_events()
        self.textaxis.axis('off')
        
    # ----------------------------------------------------------
    def show_zoom(self, candidates, llr_overlay=False, cols=3):
        """
        Create per-candidate zoom boxes (gridded subplots).
        Optionally overlay LLRs if candidate.llr is present.
        """
        n = len(candidates)
        rows = int(np.ceil(n / cols))
        zoom_fig, axes = plt.subplots(rows, cols, figsize=(3.5 * cols, 5 * rows))
        axes = np.atleast_1d(axes).flatten()
        self.zoom_axes = axes

        # Precompute Costas skeleton (symbol, tone index pairs)
        costas_pairs = [(symb_idx + offset, tone)
                        for offset in (0, 36, 72) # magic numbers; move to a 'costas object' per mode
                        for symb_idx, tone in enumerate(self.costas)]

        for i, c in enumerate(candidates):
            ax = axes[i]
            pwr = c.power_grid
            ax.imshow(
                pwr,
                origin="lower",
                aspect="auto",
                cmap="inferno",
                interpolation='none',
                norm=LogNorm()
            )
            ax.set_title(f"f={c.bounds.f0:.0f}Hz  t={c.bounds.t0:.2f}s")
            ax.set_xlabel("Tone index")
            ax.set_ylabel("Symbol")

            # --- Costas rectangles ---
            for symb_idx, tone_idx in costas_pairs:
                rect = patches.Rectangle(
                    (tone_idx - 0.5, symb_idx - 0.5), 1, 1,
                    edgecolor='lime', facecolor='none', linewidth=1.2
                )
                ax.add_patch(rect)

            if llr_overlay and c.llr is not None:
                # Normalise and reshape LLRs (174 → 58×3 pattern if needed)
                llr = np.array(c.llr, dtype=np.float32)
                llr_img = llr.reshape(-1, 3) if llr.size % 3 == 0 else llr[:, None]
                ax.imshow(
                    llr_img.T,
                    alpha=0.4,
                    cmap="bwr",
                    aspect="auto"
                )

        for ax in axes[n:]:
            ax.axis("off")

        zoom_fig.tight_layout()
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()  # <-- forces actual draw
        plt.pause(0.001)
