from dataclasses import dataclass
import numpy as np

# ============================================================
# Spectrum
# ============================================================

class Spectrum:
    def __init__(self, sample_rate, fbins_pertone, hops_persymb, sigspec):
        self.sample_rate = float(sample_rate)
        self.sigspec = sigspec
        self.fbins_pertone = int(fbins_pertone)
        self.hops_persymb = int(hops_persymb)
        self.FFT_len = int(self.fbins_pertone * self.sample_rate // self.sigspec.symbols_persec)
        self.nFreqs   = self.FFT_len // 2 + 1
        
    def fill_arrays(self, fine_grid_complex):
        self.fine_grid_complex = fine_grid_complex
        self.fine_grid_pwr = np.abs(fine_grid_complex)**2
      #  self.fine_grid_pwr = self.fine_grid_pwr / np.max(self.fine_grid_pwr)
        nHops_loaded = self.fine_grid_complex.shape[0]
        sync_headroom = nHops_loaded - self.sigspec.num_symbols*self.hops_persymb
        needed_headroom = int((self.hops_persymb * 1.5) / 0.16)
        headroom = min(sync_headroom, needed_headroom)
        sync_template_hops = self.sigspec.costas_len * self.hops_persymb
        self.hop0_range = range(headroom)
        self.extent = [0, self.sample_rate/2, 0,  (nHops_loaded / self.hops_persymb) / self.sigspec.symbols_persec ]
        self.df = self.extent[1]/self.fine_grid_complex.shape[1]
        self.dt = self.extent[3]/self.fine_grid_complex.shape[0]
        
# ============================================================
# Candidate
# ============================================================

class Candidate:
    def __init__(self, spectrum, f0_idx, size, cyclestart_str):
        self.size = size
        self.origin = (0, f0_idx)
        self.spectrum = spectrum
        self.cyclestart_str = cyclestart_str
        self.fbins = range(self.origin[1], self.origin[1] + self.size[1])
        self.fine_grid_pwr = self.spectrum.fine_grid_pwr[:,f0_idx:f0_idx + self.size[1]]

    def prep_for_decode(self, sigspec, t0):
        self.origin = (t0, self.origin[1])
        self.tbins = range(self.origin[0], self.origin[0] + self.size[0])
        self.llr = None
        self.llr_std = None
        self.payload_bits = None
        self.sigspec = sigspec  
        self.payload_bits = []
        self.message = None
        self.snr = -24
        self.origin_physical = (self.spectrum.dt * self.origin[0], self.spectrum.df * self.origin[1])
        self.fine_grid_complex = self.spectrum.fine_grid_complex[self.tbins,:][:, self.fbins] 



