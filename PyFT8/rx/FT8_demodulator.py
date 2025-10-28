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
        
    # ======================================================
    # Candidate search
    # ======================================================
    
    def find_candidates(self, t0=0.0, t1=2, f0=100.0, f1=3300.0, topN=50):
        """ wave file test
        14:27:21.25 (=0.00) Start to Load audio
        14:27:22.95 (+1.70) Start to Show spectrum
        14:27:23.31 (+0.36) Start to Find candidates
        14:27:26.38 (+3.07) Found 25 candidates
        14:27:26.40 (+0.01) Start to Show candidates
        14:27:26.72 (+0.33) Start to Demodulate
        14:27:27.28 (+0.55) Decoded 5 signals
        TEST     0.000 Rx FT8    000 -0.3 2156 WM3PEN EA6VQ -09 4 1035
        TEST     0.000 Rx FT8    000  0.0 2569 W1FC F5BZB -08 10 1233
        TEST     0.000 Rx FT8    000 -0.1  721 A92EE F5PSR -14 8 346
        TEST     0.000 Rx FT8    000  0.1  588 K1JT HA0DU KN07 11 282
        TEST     0.000 Rx FT8    000  0.0  638 N1JFU EA6EE -07 10 306
        """
        region = Bounds.from_physical(self.spectrum, t0, t1, f0, f1)
        candidates = []
        for f0_idx in region.f_idx_range:
            max_score = -1e10
            for t_idx in region.t_idx_range:
                score = self._csync_score_3(t_idx, f0_idx)
                if(score > max_score):
                    max_score = score
                    t0_idx = t_idx
            if max_score > self._csync_threshold:
                candidates.append(Candidate(self.sigspec, self.spectrum, t0_idx, f0_idx, max_score))
        # sort and de-duplicate
        candidates.sort(key=lambda c: -c.score)
        min_sep_fbins = 0.5 * self.sigspec.tones_persymb * self.fbins_pertone
        uniq = []
        for c in candidates:
            if not any(abs(c.bounds.f0_idx - u.bounds.f0_idx) < min_sep_fbins for u in uniq):
                uniq.append(c)
        return uniq[:topN]

    def _csync_score(self, t0_idx, f0_idx):
        return np.sum(self._csync * self.spectrum.power[t0_idx:t0_idx + self._csync.shape[0], f0_idx:f0_idx + self._csync.shape[1]])

    def _csync_score_3(self, t0_idx, f0_idx):
        score = 0.0
        for symb_idx in [0, 36, 72]: # magic numbers; move to a 'costas object' per mode
            t_idx = t0_idx + symb_idx * self.hops_persymb
            block_score = np.sum(self._csync * self.spectrum.power[t_idx:t_idx + self._csync.shape[0], f0_idx:f0_idx + self._csync.shape[1]])
            score = block_score if block_score > score else score
            #score += block_score
        return score 

    # ======================================================
    # Demodulation
    # ======================================================
    def demodulate(self, candidates, cyclestart_str):
        out = []
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72)) # move this to sigspec
        for c in candidates:
            # try getting payload symbols' tones & bits from max of each symbol's tone powers
            pgrid = c.power_grid
         #   tone_numbs = [int(np.argmax(pgrid[symbol_idx, :])) for symbol_idx in payload_symb_idxs]
         #   bits = [b for tone_numb in tone_numbs for b in FT8.gray_map_tuples[tone_numb]]
         #   if crc.check_crc(crc.bitsLE_to_int(bits[0:91])):
         #       c.demodulated_by = 'Max power'
         #       c.payload_bits = bits
         #       out.append(FT8_decode(c, cyclestart_str))
         #       continue
            # if that didn't pass crc, try getting llrs and feeding to ldpc
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
    dict_line = {'cyclestart_str':cyclestart_str , 'freq':freq_str, 'call_a':call_a, 'call_b':call_b, 'grid_rpt':grid_rpt, 'bounds':signal.bounds}
    return dict_line, all_txt_line

