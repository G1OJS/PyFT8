"""
datagrids.py
-------------
Core data structures for representing 2-D spectral data
(time–frequency grids) used by FT8, FT4, WSPR, etc.

Classes:
    Bounds     – defines index/physical coordinate limits for 2D data
    Spectrum   – owns the complex FFT grid and derived quantities
    Candidate  – represents a rectangular region of interest
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
        self.FFT_len = int(self.fbins_pertone * self.sample_rate // self.symbols_persec)
        self.nFreqs   = self.FFT_len // 2 + 1
        self.width_Hz = self.sample_rate / 2
        self.df       = self.width_Hz / (self.nFreqs - 1)
        
        # ---- Time geometry ----
        self.nHops = int(self.hops_persymb * self.symbols_persec * self.frame_secs)
        self.nSymbols = int(self.symbols_persec * self.frame_secs)
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

        # ---- Spectrum ----
        self.fine_grid_complex = None

    def load_audio(self, audio_in):
        self.nHops = int(self.hops_persymb * self.symbols_persec * (len(audio_in) - self.FFT_len)/self.sample_rate)
        self.fine_grid_complex = np.zeros((self.nHops, self.nFreqs), dtype = np.complex64)
        for hop_idx in range(self.nHops):
            sample_idx = int(hop_idx * self.sample_rate / (self.symbols_persec * self.hops_persymb))
            aud = audio_in[sample_idx:sample_idx + self.FFT_len] * np.kaiser(self.FFT_len,14)
            self.fine_grid_complex[hop_idx,:] = np.fft.rfft(aud)[:self.nFreqs]


# ============================================================
# Bounds
# ============================================================

@dataclass
class Bounds:
    def __init__(self,  t0_idx, tn_idx, f0_idx, fn_idx, t0, tn, f0, fn):
        self.t0_idx, self.tn_idx = int(t0_idx), int(tn_idx)
        self.f0_idx, self.fn_idx = int(f0_idx), int(fn_idx)
        self.t0, self.tn = t0, tn
        self.f0, self.fn = f0, fn

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
        self.llr_std = None
        self.payload_symb_idxs = sigspec.payload_symb_idxs
        self.score = score
        self.snr = -24
        tn_idx = t0_idx + sigspec.num_symbols * spectrum.hops_persymb
        fn_idx = f0_idx + sigspec.tones_persymb * spectrum.fbins_pertone
        self.bounds = Bounds(t0_idx, tn_idx, f0_idx, fn_idx,
                             t0_idx * spectrum.dt, tn_idx * spectrum.dt,
                             f0_idx * spectrum.df, fn_idx * spectrum.df)
        self.cycle_start = cycle_start
        self.payload_bits = []
        self.message = None
        self.fine_grid_complex = spectrum.fine_grid_complex [ t0_idx : tn_idx, f0_idx : fn_idx]


    def update_t0_idx(self, t0_idx):
        delta = t0_idx - self.bounds.t0_idx
        self.bounds.t0_idx += delta
        self.bounds.tn_idx += delta
    


