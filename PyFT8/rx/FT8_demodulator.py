"""
FT8_demodulator.py
------------------
Audio → spectrum → Candidates → Bits.

Refactored to use new datagrids framework:
    spectrum / Candidate / Bounds.with_from_physical()
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
        # ---- Configuration ----
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec
        self.max_t0_idx = int(self.hops_persymb * 2.0 *6.25)
        # ---- spectrum setup ----
        self.spectrum = Spectrum( fbins_pertone=self.fbins_pertone, hops_persymb=self.hops_persymb,
                                  sample_rate=self.sample_rate, sigspec=self.sigspec)
        # ---- FFT precompute ----
        self.FFT_size = self.spectrum.FFT_size
        self._hop_size = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb)) 
        # ---- Costas sync mask ----
        costas = [3, 1, 4, 0, 6, 5, 2]
        h, w = 7 * self.hops_persymb, 8 * self.fbins_pertone
        self._csync = np.full((h, w), -1/7, np.float32)
        for sym_idx, tone in enumerate(costas):
            t0 = sym_idx * self.hops_persymb
            f0 = tone * self.fbins_pertone
            self._csync[t0:t0+self.hops_persymb, f0:f0+self.fbins_pertone] = 1.0
        self._csync_threshold = 1e5

    def demod_rxFreq(self, rxFreq, cycle_str):
        candidates = []
        f0_idx = int(np.searchsorted(self.spectrum.freqs, rxFreq))
        candidates.append(Candidate(self.sigspec, self.spectrum, 0, f0_idx, -50))
        candidates = self.sync_candidates(candidates, topN=1)
        decode = self.demodulate(candidates, cyclestart_str = cycle_str)
        return decode
                     
    # ======================================================
    # Candidate search
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
        uniq = []
        for c in candidates:
            if not any(abs(c.bounds.f0_idx - u.bounds.f0_idx) < min_sep_fbins for u in uniq):
                uniq.append(c)
        return uniq[:topN]
    
    def sync_candidates(self, candidates, topN=25):
        """ wave file test
        19:38:23.13 (=0.00) Start to Load audio
        19:38:23.50 (+0.37) Start to Show spectrum
        19:38:23.82 (+0.33) Start to Find candidates
        19:38:23.89 (+0.07) Found 500 candidates
        19:38:23.90 (+0.01) Start to deduplicate candidate frequencies
        19:38:23.92 (+0.02) Now have 40 candidates
        19:38:23.93 (+0.01) Start to sync candidates
        19:38:24.03 (+0.10) Synced 30 candidates
        19:38:24.07 (+0.04) Start to Show candidates
        19:38:24.41 (+0.34) Start to Demodulate
        19:38:25.58 (+1.17) Decoded 5 signals
        """
        for c in candidates:
            c.score = -1e10
            for t0_idx in range(self.spectrum.nHops - self.sigspec.num_symbols*self.hops_persymb-1):
                score = self._csync_score_3(t0_idx, c.bounds.f0_idx)
                if(score > c.score):
                    c.score = score
                    c.update_t0_idx(t0_idx)
        # sort and de-duplicate
        candidates.sort(key=lambda c: -c.score)
        
        return candidates[:topN]


    def _csync_score(self, t0_idx, f0_idx):
        return np.sum(self._csync * self.spectrum.power[t0_idx:t0_idx + self._csync.shape[0], f0_idx:f0_idx + self._csync.shape[1]])

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
    def demodulate(self, candidates, cyclestart_str):
        out = []
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72)) # move this to sigspec
        for c in candidates:
            pgrid = c.power_grid
            LLR174s = []
            for symb_idx in payload_symb_idxs:
                sigma2 = np.median(self.spectrum.power[symb_idx*self.hops_persymb,:]) 
                tone_powers_scaled = pgrid[symb_idx, :] / sigma2
                for k in range(3):
                    s1 = [v for i, v in enumerate(tone_powers_scaled) if FT8.gray_map_tuples[i][k]]
                    s0 = [v for i, v in enumerate(tone_powers_scaled) if not FT8.gray_map_tuples[i][k]]
                    m1 = max(s1)
                    m0 = max(s0)
                    s1v = m1 + math.log(np.sum(np.exp(np.array(s1) - m1)))
                    s0v = m0 + math.log(np.sum(np.exp(np.array(s0) - m0)))
                    LLR174s.append(s1v - s0v)
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
   # snr = r-35 if r<=85 else r-35-101
   # if(snr>50): return ''
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

