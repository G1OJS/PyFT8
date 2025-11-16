from dataclasses import dataclass
import numpy as np

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
# Spectrum
# ============================================================

class Spectrum:

    def __init__(self, sample_rate, fbins_pertone, hops_persymb, sigspec):
        self.sample_rate = float(sample_rate)
        self.sigspec = sigspec
        self.fbins_pertone = int(fbins_pertone)
        self.hops_persymb = int(hops_persymb)
        self.nHops = None
        self.sync_hop0s = None
        self.fine_grid_complex = None
        self.FFT_len = int(self.fbins_pertone * self.sample_rate // self.sigspec.symbols_persec)
        self.nFreqs   = self.FFT_len // 2 + 1
        self.dt = 1 / (self.sigspec.symbols_persec * self.hops_persymb)
        self.df = self.sample_rate / self.FFT_len
        
    def set_bounds(self, nHops):
        self.nHops = nHops
        self.bounds = Bounds(
            0, self.nHops,
            0, self.nFreqs,
            0, (self.nHops+1)*self.dt,
            0, (self.nFreqs+1)*self.df
        )
        sync_template_nHops = self.sigspec.num_symbols*self.hops_persymb
        sync_headroom = self.nHops - sync_template_nHops
        needed_headroom = int((self.hops_persymb * 1.5) / 0.16)
        headroom = min(sync_headroom, needed_headroom)
        self.sync_hop0s = range(headroom)
        self.sync_hops = range(headroom + sync_template_nHops)

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
        self.cycle_start = cycle_start
        self.payload_bits = []
        self.message = None
        self.update_bounds(spectrum, sigspec, t0_idx, f0_idx)
   
    def update_bounds(self, spectrum, sigspec, t0_idx, f0_idx):
        tn_idx = t0_idx + sigspec.num_symbols * spectrum.hops_persymb
        fn_idx = f0_idx + sigspec.tones_persymb * spectrum.fbins_pertone
        self.bounds = Bounds(t0_idx, tn_idx, f0_idx, fn_idx,
                             t0_idx * spectrum.dt, tn_idx * spectrum.dt,
                             f0_idx * spectrum.df, fn_idx * spectrum.df)

    


