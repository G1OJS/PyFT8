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
    """Defines index and physical coordinate limits for a 2-D grid."""
    t0_idx: int
    tn_idx: int
    f0_idx: int
    fn_idx: int
    t0: float
    tn: float
    f0: float
    fn: float

    # ---- Convenience properties ----
    @property
    def extent(self):
        """Extent in matplotlib imshow format: [xleft, xright, ybottom, ytop]."""
        return [self.f0, self.fn, self.t0, self.tn]

    @property
    def t_range(self):
        """Range of time indices."""
        return range(self.t0_idx, self.tn_idx)

    @property
    def f_range(self):
        """Range of frequency indices."""
        return range(self.f0_idx, self.fn_idx)

    @property
    def width_f(self):
        return self.fn - self.f0

    @property
    def height_t(self):
        return self.tn - self.t0


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
    """
    Represents a rectangular region of interest within a Spectrum.
    Typically used for a detected FT8/FT4 signal candidate.
    """

    def __init__(self, spectrum, t0_idx, tn_idx, f0_idx, fn_idx):
        self.spectrum = spectrum
        t = spectrum.times
        f = spectrum.freqs
        dt, df = spectrum.dt, spectrum.df
        self.bounds = Bounds(
            t0_idx, tn_idx, f0_idx, fn_idx,
            t[t0_idx], t[tn_idx - 1] + dt,
            f[f0_idx], f[fn_idx - 1] + df
        )

    def extract_power(self):
        """Return power subgrid for this candidate."""
        t0, tn = self.bounds.t0_idx, self.bounds.tn_idx
        f0, fn = self.bounds.f0_idx, self.bounds.fn_idx
        return self.spectrum.power[t0:tn, f0:fn]


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
