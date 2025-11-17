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
        nHops_loaded = self.fine_grid_complex.shape[0]
        sync_headroom = nHops_loaded - self.sigspec.num_symbols*self.hops_persymb
        needed_headroom = int((self.hops_persymb * 1.5) / 0.16)
        headroom = min(sync_headroom, needed_headroom)
        sync_template_hops = self.sigspec.costas_len * self.hops_persymb
        self.hop0_range = range(headroom)
        self.fine_abs_search1 = np.abs(self.fine_grid_complex[:headroom + sync_template_hops,:])
        self.extent = [0, self.sample_rate/2, 0,  (nHops_loaded / self.hops_persymb) / self.sigspec.symbols_persec ]
        self.df = self.extent[1]/self.fine_grid_complex.shape[1]
        self.dt = self.extent[3]/self.fine_grid_complex.shape[0]
        
# ============================================================
# Candidate
# ============================================================

class Candidate:
    def __init__(self, sigspec, spectrum, origin, score=None, cyclestart_str='xxxxxx_xxxxxx'):
        self.llr = None
        self.llr_std = None
        self.payload_bits = None
        self.spectrum = spectrum
        self.sigspec = sigspec
        self.score = score
        self.snr = -24
        self.cyclestart_str = cyclestart_str
        self.payload_bits = []
        self.message = None
        self.set_origin(origin)

    def set_origin(self, origin):
        self.origin = origin
        self.origin_physical = (self.spectrum.dt * origin[0], self.spectrum.df * origin[1])
        self.tbins = range(self.origin[0], self.origin[0] + self.sigspec.num_symbols * self.spectrum.hops_persymb)
        self.fbins = range(self.origin[1], self.origin[1] + self.sigspec.tones_persymb * self.spectrum.fbins_pertone)
   
    def fill_arrays(self, new_origin = None):
        if(new_origin): self.set_origin(new_origin)
        self.fine_grid_complex = self.spectrum.fine_grid_complex[self.tbins,:][:, self.fbins] 
    


