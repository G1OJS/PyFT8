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
# Spectrum
# ============================================================

class Spectrum:
    """
    Represents a complete time–frequency grid of complex FFT data.
    Handles grid geometry (dt, df, FFT size) and provides derived
    views such as .power and .energy().
    """

    def __init__(self, sample_rate, fbins_pertone, hops_persymb, sigspec):
        """
        Parameters
        ----------
        sample_rate : float
            Audio sample rate (Hz)
        fbins_pertone : int
            Frequency bins per tone (frequency resolution multiplier)
        hops_persymb : int
            Time hops per symbol (time resolution multiplier)
        sigspec : SignalSpec
            Signal definition (frame_secs, symbols_persec, etc.)
        """
        self.sample_rate = float(sample_rate)
        self.sigspec = sigspec
        self.fbins_pertone = int(fbins_pertone)
        self.hops_persymb = int(hops_persymb)

        # ---- Derived from SignalSpec ----
        self.frame_secs     = sigspec.frame_secs
        self.symbols_persec = sigspec.symbols_persec
        self.num_symbols    = sigspec.num_symbols
        self.tones_persymb  = sigspec.tones_persymb
        self.costas         = sigspec.costas

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
        self.bounds = Bounds(self,
            0, self.nHops, 0, self.nFreqs,
            self.times[0], self.times[-1] + self.dt,
            self.freqs[0], self.freqs[-1] + self.df
        )

        # ---- Data arrays ----
        self.complex = np.zeros((self.nHops, self.nFreqs), np.complex64)
        self.power = np.zeros((self.nHops, self.nFreqs), np.float32)

    def feed_audio(self, audio: np.ndarray):
        """ Fill complex from a block of real audio samples. """
        for hop_idx in range(self.nHops):
            sample_idx0 = int(hop_idx * self.sample_rate / (self.symbols_persec * self.hops_persymb))
            sample_idxn = sample_idx0 + self.FFT_size
            if(sample_idxn < len(audio)):
                self.complex[hop_idx,:] = np.fft.rfft(audio[sample_idx0:sample_idxn] * np.kaiser(self.FFT_size,14))
                self.power = np.abs(self.complex) ** 2


# ============================================================
# Bounds
# ============================================================

@dataclass
class Bounds:
    def __init__(self, spectrum, t0_idx, tn_idx, f0_idx, fn_idx, t0=None, tn=None, f0=None, fn=None):
        self.t0_idx, self.tn_idx = int(t0_idx), int(tn_idx)
        self.f0_idx, self.fn_idx = int(f0_idx), int(fn_idx)
        self.t0, self.tn = spectrum.times[t0_idx] if t0 is None else float(t0), spectrum.times[tn_idx] if tn is None else float(tn) 
        self.f0, self.fn = spectrum.freqs[f0_idx] if f0 is None else float(f0), spectrum.freqs[fn_idx] if fn is None else float(fn)

    @classmethod
    def from_physical(cls, spectrum, t0=None, t1=None, f0=None, f1=None):
        t0_idx, t1_idx = int(np.searchsorted(spectrum.times, t0)), int(np.searchsorted(spectrum.times, t1))
        f0_idx, f1_idx = int(np.searchsorted(spectrum.freqs, f0)), int(np.searchsorted(spectrum.freqs, f1))
        return cls(spectrum, t0_idx, t1_idx, f0_idx, f1_idx, t0, t1, f0, f1)
    @property
    def t_idx_range(self): return range(self.t0_idx, self.tn_idx)
    @property
    def f_idx_range(self): return range(self.f0_idx, self.fn_idx)
    @property
    def nTimes(self): return len(self.t_idx_range)
    @property
    def nFreqs(self): return len(self.f_idx_range)
    @property
    def extent(self):
        """Matplotlib extent = [xleft, xright, ybottom, ytop]."""
        return [self.f0, self.fn, self.t0, self.tn]

                
# ============================================================
# Candidate
# ============================================================


class Candidate:
    def __init__(self, sigspec, spectrum, t0_idx, f0_idx, score=None, cycle_start=None, demodulated_by=None):
        self.llr = None
        self.payload_bits = []
        self.payload_symbols = []
        self.score = score
        self.sigspec = sigspec
        self.spectrum = spectrum
        self.bounds = Bounds(spectrum, t0_idx, t0_idx + sigspec.num_symbols * spectrum.hops_persymb,
                                       f0_idx, f0_idx + sigspec.tones_persymb * spectrum.fbins_pertone)
        self.cycle_start = cycle_start
        self.demodulated_by = demodulated_by

    @property
    def power_grid(self):
        norm = 1.0 / (self.spectrum.hops_persymb * self.spectrum.fbins_pertone)
        t0_idx, tn_idx = self.bounds.t0_idx, self.bounds.tn_idx
        f0_idx, fn_idx = self.bounds.f0_idx, self.bounds.fn_idx
        
        sub = self.spectrum.power[t0_idx:tn_idx, f0_idx:fn_idx]
        ntFine, nfFine = sub.shape
        ntTrim = ntFine - (ntFine % self.spectrum.hops_persymb)
        nfTrim = nfFine - (nfFine % self.spectrum.fbins_pertone)
        sub = sub[:ntTrim, :nfTrim]
        nTimes = ntTrim // self.spectrum.hops_persymb
        nFreqs = nfTrim // self.spectrum.fbins_pertone
        sub = sub.reshape(nTimes, self.spectrum.hops_persymb, nFreqs, self.spectrum.fbins_pertone)

        pgrid = norm * sub.sum(axis=(1, 3))
        return pgrid.astype(np.float32)
        

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
