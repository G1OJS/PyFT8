"""
wave file test
10:32:11.62 (=0.00) Start to Load audio from 210703_133430.wav
10:32:12.02 (+0.40) Start to Show spectrum
10:32:12.34 (+0.31) Start to Find candidates
10:32:12.45 (+0.11) Found 500 candidates
10:32:12.50 (+0.06) Start to deduplicate candidate frequencies
10:32:12.53 (+0.02) Now have 40 candidates
10:32:12.54 (+0.01) Start to sync candidates
10:32:12.64 (+0.10) Synced 30 candidates
10:32:12.68 (+0.04) Start to Show candidates
10:32:13.01 (+0.34) Start to demodulate candidates
10:32:14.06 (+1.05) Decodes: 6
Test     0.000 Rx FT8    000 -0.3 2154 WM3PEN EA6VQ -09 4
Test     0.000 Rx FT8    000  0.0 2569 W1FC F5BZB -08 10
Test     0.000 Rx FT8    000 -0.1  721 A92EE F5PSR -14 8
Test     0.000 Rx FT8    000  0.1  588 K1JT HA0DU KN07 11
Test     0.000 Rx FT8    000  0.0  638 N1JFU EA6EE -07 10
Test     0.000 Rx FT8    000 -0.1 1646 K1JT EA3AGB -15 7
"""

import math
import numpy as np
from scipy.signal import correlate2d, find_peaks

from PyFT8.datagrids import Spectrum, Bounds, Candidate
from PyFT8.signaldefs import FT8
from PyFT8.rx.decode174_91 import decode174_91
import PyFT8.FT8_crc as crc

class FT8Demodulator:
    def __init__(self, sample_rate=12000, fbins_pertone=3, hops_persymb=3, sigspec=FT8):
        # ft8c.f90 uses 4 hops per symbol and 2.5Hz fbins (2.5 bins per tone)
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec
        self.max_t0_idx = int(self.hops_persymb * 2.0 *6.25)
        # ---- spectrum setup ----
        self.spectrum = Spectrum( fbins_pertone=self.fbins_pertone, hops_persymb=self.hops_persymb,
                                  sample_rate=self.sample_rate, sigspec=self.sigspec)
        # ---- FFT params ----
        self.FFT_size = self.spectrum.FFT_size
        self._hop_size = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb)) 
        # ---- Costas sync mask ----
        h, w = self.sigspec.costas_len * self.hops_persymb, self.sigspec.tones_persymb * self.fbins_pertone
        self._csync = np.full((h, w), -1/7, np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            t0 = sym_idx * self.hops_persymb
            f0 = tone * self.fbins_pertone
            self._csync[t0:t0+self.hops_persymb, f0:f0+self.fbins_pertone] = 1.0
               
    # ======================================================
    # Candidate search and sync
    # ======================================================

    def find_candidates(self, f0, f1, topN=25):
        region = Bounds.from_physical(self.spectrum, 0, 15, f0, f1)
        candidates = []
        for f0_idx in region.f_idx_range:
            score = np.sum(self.spectrum.power[: , f0_idx:f0_idx+self._csync.shape[1]])
            candidates.append(Candidate(self.sigspec, self.spectrum, 0, f0_idx, score))
        candidates.sort(key=lambda c: -c.score)
        return candidates[:topN]

    def deduplicate_candidate_freqs(self, candidates, topN=25 ):
        min_sep_fbins = 0.5 * self.sigspec.tones_persymb * self.fbins_pertone
        deduplicated = []
        for c in candidates:
            keep_c = True
            for i, existing in enumerate(deduplicated):
                if abs(c.bounds.f0_idx - existing.bounds.f0_idx) < min_sep_fbins:
                    if c.score > existing.score * 1.3:  # >~1.1–1.3× stronger
                        deduplicated[i] = c
                    keep_c = False
                    break
            if keep_c:
                deduplicated.append(c)
        return deduplicated[:topN]
    
    def sync_candidates(self, candidates, topN=25):
        for c in candidates:
            c.score = -1e10
            for t0_idx in range(self.spectrum.nHops - self.sigspec.num_symbols*self.hops_persymb-1):
                score = self._csync_score_3(t0_idx, c.bounds.f0_idx)
                if(score > c.score):
                    c.score = score
                    c.update_t0_idx(t0_idx)
        candidates.sort(key=lambda c: -c.score)
        return candidates[:topN]

    def _csync_score_3(self, t0_idx, f0_idx):
        score = 0.0
        fn_idx = f0_idx + self._csync.shape[1]
        nt = self._csync.shape[0]
        block_hopstarts = [0, 36 * self.hops_persymb, 72 * self.hops_persymb]
        for block_idx in block_hopstarts: 
            t_idx = t0_idx + block_idx
            pgrid = self.spectrum.power[t_idx:t_idx + nt, f0_idx:fn_idx]
            block_score = np.sum(pgrid * self._csync)
            if block_score > score: score = block_score 
        return score 

    # ======================================================
    # Demodulation
    # ======================================================

    def demod_rxFreq(self, rxFreq, cycle_str):
        candidates = []
        f0_idx = int(np.searchsorted(self.spectrum.freqs, rxFreq))
        candidates.append(Candidate(self.sigspec, self.spectrum, 0, f0_idx, -50))
        candidates = self.sync_candidates(candidates, topN=1)
        decode = self.demodulate(candidates, cyclestart_str = cycle_str)
        return decode
    
    def demodulate(self, candidates, cyclestart_str):
        out = []
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72)) # move this to sigspec
        for c in candidates:
            LLR174s=[]
            pgrid = self.spectrum.power[c.bounds.t0_idx:  c.bounds.t0_idx + c.sigspec.num_symbols * self.hops_persymb,
                                        c.bounds.f0_idx : c.bounds.f0_idx + 8*self.fbins_pertone]
            pgrid = pgrid.reshape(c.sigspec.num_symbols, self.hops_persymb, 8, self.fbins_pertone).mean(axis=(1,3))
            gray_mask = self.sigspec.gray_mask
            for symb_idx in payload_symb_idxs:
                sigma2 = self.spectrum.noise_per_symb[symb_idx]
                tone_powers_scaled = pgrid[symb_idx, :] / sigma2
                m1 = np.where(gray_mask, tone_powers_scaled[:, None], -np.inf)
                m0 = np.where(~gray_mask, tone_powers_scaled[:, None], -np.inf)
                LLR_sym = np.logaddexp.reduce(m1, axis=0) - np.logaddexp.reduce(m0, axis=0)
                LLR174s.extend(LLR_sym)
                
            ncheck, bits, n_its = decode174_91(LLR174s)
            if(ncheck == 0):
                c.demodulated_by = f"LLR-LDPC ({n_its})"
                c.payload_bits = bits
                out.append(FT8_decode(c, cyclestart_str))
        return out

# ======================================================
# FT8 Unpacking functions
# ======================================================

def unpack_ft8_c28(c28):
    from string import ascii_uppercase as ltrs, digits as digs
    if c28<3: return ["DE", 'QRZ','CQ'][c28]
    n = c28 - 2_063_592 - 4_194_304 # NTOKENS, MAX22
    if n >= 0:
        charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
        divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
        indices = []
        for d in divisors:
            i, n = divmod(n, d)
            indices.append(i)
        callsign = ''.join(t[i] for t, i in zip(charmap, indices)).lstrip()
        return callsign.strip()
    return '<...>'

def unpack_ft8_g15(g15):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    return f"{snr:+03d}"

def FT8_decode(signal, cyclestart_str):
    # need to add support for /P and R+report (R-05)
    bits = signal.payload_bits
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
    c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
    g15  = int(''.join(str(b) for b in bits[59:74]), 2)
    call_a = unpack_ft8_c28(c28_a)
    call_b =  unpack_ft8_c28(c28_b)
    grid_rpt = unpack_ft8_g15(g15)
    freq_str = f"{signal.bounds.f0:4.0f}"
    all_txt_line = f"{cyclestart_str}     0.000 Rx FT8    000 {signal.bounds.t0 - 0.5 :4.1f} {signal.bounds.f0 :4.0f} {call_a} {call_b} {grid_rpt}"
    dict_line = {'cyclestart_str':cyclestart_str , 'freq':freq_str, 'call_a':call_a,
                 'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':signal.bounds.t0_idx}
    return dict_line, all_txt_line

