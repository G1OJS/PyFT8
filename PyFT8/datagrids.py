"""
datagrids.py
-------------
Core data structures for representing 2-D spectral data
(time–frequency grids) used by FT8, FT4, WSPR, etc.

Classes:
    Bounds     – defines index/physical coordinate limits for 2D data
    Spectrum   – owns the complex FFT grid and derived quantities
    Candidate  – represents a rectangular region of interest
    Waterfall  – provides a visual or logical view over a Spectrum
"""

from dataclasses import dataclass
import numpy as np


# ============================================================
# Bounds
# ============================================================

@dataclass
class Bounds:
    def __init__(self, t0_idx, tn_idx, f0_idx, fn_idx,
                 t0=None, tn=None, f0=None, fn=None):
        self.t0_idx, self.tn_idx = int(t0_idx), int(tn_idx)
        self.f0_idx, self.fn_idx = int(f0_idx), int(fn_idx)
        self.t0, self.tn = float(t0) if t0 is not None else None, float(tn) if tn is not None else None
        self.f0, self.fn = float(f0) if f0 is not None else None, float(fn) if fn is not None else None

    # ------------------------------------------------------
    # Alternate constructors
    # ------------------------------------------------------
    @classmethod
    def from_physical(cls, spectrum, t0=None, t1=None, f0=None, f1=None):
        """
        Build a Bounds from physical time/frequency limits.
        """
        times, freqs = spectrum.times, spectrum.freqs
        t0 = 0 if t0 is None else float(t0)
        t1 = times[-1] if t1 is None else float(t1)
        f0 = 0 if f0 is None else float(f0)
        f1 = freqs[-1] if f1 is None else float(f1)

        t0_idx = int(np.searchsorted(times, t0))
        t1_idx = int(np.searchsorted(times, t1))
        f0_idx = int(np.searchsorted(freqs, f0))
        f1_idx = int(np.searchsorted(freqs, f1))
        return cls(t0_idx, t1_idx, f0_idx, f1_idx, t0, t1, f0, f1)

    @classmethod
    def full(cls, spectrum):
        """Convenience: entire spectrum area."""
        return cls.from_physical(spectrum)

    # ------------------------------------------------------
    # Derived convenience
    # ------------------------------------------------------
    @property
    def t_range(self): return range(self.t0_idx, self.tn_idx)
    @property
    def f_range(self): return range(self.f0_idx, self.fn_idx)

    @property
    def extent(self):
        """Matplotlib extent = [xleft, xright, ybottom, ytop]."""
        return [self.f0, self.fn, self.t0, self.tn]

    def clamp_to(self, spectrum):
        """Clamp indices to valid spectrum extents."""
        self.tn_idx = min(self.tn_idx, spectrum.nHops)
        self.fn_idx = min(self.fn_idx, spectrum.nFreqs)
        return self

    def contains_window(self, t_idx: int, f_idx: int, window_shape):
        """
        Return True if a rectangular window (of shape (height, width))
        positioned with its top-left corner at (t_idx, f_idx)
        fits fully inside these bounds.
        """
        h, w = window_shape
        return (
            t_idx >= self.t0_idx and
            f_idx >= self.f0_idx and
            (t_idx + h) <= self.tn_idx and
            (f_idx + w) <= self.fn_idx
        )


# ============================================================
# Spectrum
# ============================================================

class Spectrum:
    """
    Represents a complete time–frequency grid of complex FFT data.
    Handles grid geometry (dt, df, FFT size) and provides derived
    views such as .power and .energy().
    """

    def __init__(self, sample_rate, fbins_pertone, hops_persymb, spec):
        """
        Parameters
        ----------
        sample_rate : float
            Audio sample rate (Hz)
        fbins_pertone : int
            Frequency bins per tone (frequency resolution multiplier)
        hops_persymb : int
            Time hops per symbol (time resolution multiplier)
        spec : SignalSpec
            Signal definition (frame_secs, symbols_persec, etc.)
        """
        self.sample_rate = float(sample_rate)
        self.spec = spec
        self.fbins_pertone = int(fbins_pertone)
        self.hops_persymb = int(hops_persymb)

        # ---- Derived from SignalSpec ----
        self.frame_secs     = spec.frame_secs
        self.symbols_persec = spec.symbols_persec
        self.num_symbols    = spec.num_symbols
        self.tones_persymb  = spec.tones_persymb
        self.costas         = spec.costas

        # ---- FFT geometry ----
        self.FFT_size = int(self.fbins_pertone * self.sample_rate // self.symbols_persec)
        self.nFreqs   = self.FFT_size // 2 + 1
        self.width_Hz = self.sample_rate / 2
        self.df       = self.width_Hz / (self.nFreqs - 1)

        # ---- Time geometry ----
        self.nHops = int(self.hops_persymb * self.symbols_persec * self.frame_secs)
        self.dt = self.frame_secs / (self.nHops - 1)

        # ---- Coordinate arrays (bin centres) ----
        self.times = np.arange(self.nHops) * self.dt
        self.freqs = np.arange(self.nFreqs) * self.df

        # ---- Physical bounds (edges) ----
        self.bounds = Bounds(
            0, self.nHops, 0, self.nFreqs,
            self.times[0], self.times[-1] + self.dt,
            self.freqs[0], self.freqs[-1] + self.df
        )

        # ---- Data arrays ----
        self.complex = np.zeros((self.nHops, self.nFreqs), np.complex64)

    # ---- Derived quantities ----
    @property
    def power(self):
        """Power per bin (|complex|^2)."""
        return np.abs(self.complex) ** 2

    def energy(self):
        """Total integrated energy (∑|X|²·dt·df)."""
        return np.sum(self.power) * self.dt * self.df


# ============================================================
# Candidate
# ============================================================

class Candidate:
    def __init__(self, spectrum, t0_idx, tn_idx, f0_idx, fn_idx):
        self.spectrum = spectrum
        self.bounds = Bounds(t0_idx, tn_idx, f0_idx, fn_idx,
                             spectrum.times[t0_idx],
                             spectrum.times[min(tn_idx, spectrum.nHops - 1)],
                             spectrum.freqs[f0_idx],
                             spectrum.freqs[min(fn_idx, spectrum.nFreqs - 1)])
        # data & results
        self.power_grid = None
        self.llr = None
        self.payload_bits = []
        self.payload_symbols = []
        self.freq = None
        self.dt = None

        # score tracking
        self._score = float("-inf")
        self._best_score = float("-inf")

    # ------------------------------------------------------
    # Score property
    # ------------------------------------------------------
    @property
    def score(self) -> float:
        """Latest computed search/detection score."""
        return self._score

    @score.setter
    def score(self, value: float):
        """Assign and update best_score if higher."""
        self._score = float(value)
        if value > self._best_score:
            self._best_score = float(value)

    @property
    def best_score(self) -> float:
        """Highest score seen so far (sticky max)."""
        return self._best_score

    def move_to(self, t0_idx: int, f0_idx: int):
        """Re-position candidate bounds and clamp to Spectrum extents."""
        h = self.bounds.tn_idx - self.bounds.t0_idx
        w = self.bounds.fn_idx - self.bounds.f0_idx
        self.bounds.t0_idx = int(t0_idx)
        self.bounds.f0_idx = int(f0_idx)
        self.bounds.tn_idx = min(self.bounds.t0_idx + h, self.spectrum.nHops)
        self.bounds.fn_idx = min(self.bounds.f0_idx + w, self.spectrum.nFreqs)
        # update physical
        self.bounds.t0 = self.spectrum.times[self.bounds.t0_idx]
        self.bounds.tn = self.spectrum.times[self.bounds.tn_idx - 1]
        self.bounds.f0 = self.spectrum.freqs[self.bounds.f0_idx]
        self.bounds.fn = self.spectrum.freqs[self.bounds.fn_idx - 1]

    def copy(self):
        import copy
        return copy.deepcopy(self)

    freeze = copy



# ============================================================
# Waterfall
# ============================================================

class Waterfall:
    """
    A visual or analytical view over a Spectrum.
    """
    def __init__(self, spectrum):
        self.spectrum = spectrum
        self.bounds = spectrum.bounds

    def imshow_args(self):
        """Return (data, extent) tuple for matplotlib imshow()."""
        return self.spectrum.power, self.bounds.extent
