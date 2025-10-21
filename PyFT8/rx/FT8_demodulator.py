"""
FT8_demodulator.py
------------------
Audio → spectrum → Candidates → Bits.

Refactored to use new datagrids framework:
    spectrum / Candidate / Bounds.with_from_physical()
"""

import math
import numpy as np

from PyFT8.datagrids import Spectrum, Bounds, Candidate
from PyFT8.signaldefs import FT8
from PyFT8.rx.ldpc import decode174_91
from PyFT8.rx.FT8_decoder import FT8_decode
from PyFT8.FT8_constants import kGRAY_MAP_TUPLES
# from PyFT8.bitfield import BitField  # later, for CRC

class FT8Demodulator:
    def __init__(self, sample_rate=12000, fbins_pertone=3, hops_persymb=3, sigspec=FT8):
        # ---- Configuration ----
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec

        # ---- spectrum setup ----
        self.spectrum = Spectrum(
            sample_rate=self.sample_rate,
            fbins_pertone=self.fbins_pertone,
            hops_persymb=self.hops_persymb,
            sigspec=self.sigspec
        )

        # ---- FFT precompute ----
        self.FFT_size = self.spectrum.FFT_size
        self._hop_size = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb)) 

        # ---- Costas sync mask ----
        self._csync = self._generate_csync()

    # ======================================================
    # Candidate search
    # ======================================================
    def find_candidates(self, t0=0.0, t1=1.5, f0=100.0, f1=3300.0, topN=50):
        """ Sweep a time/freq region for Costas sync patterns.
            Returns list of Candidate objects fully set.
        """
        region = Bounds.from_physical(self.spectrum, t0, t1, f0, f1)
        candidates = []
        for f0_idx in region.f_idx_range:
            max_score = -1e10
            for t_idx in region.t_idx_range:
                score = self._csync_score(t_idx, f0_idx)
                if(score > max_score):
                    max_score = score
                    t0_idx = t_idx
            if max_score > 0:
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
        score = 0.0
        for symb_idx in [0, 36, 72]:
            t_idx = t0_idx + symb_idx * self.hops_persymb
            block_score = np.sum(self._csync * np.abs(self.spectrum.complex[t_idx:t_idx + self._csync.shape[0], f0_idx:f0_idx + self._csync.shape[1]]))
            #score = block_score if block_score > score else score
            score += block_score
        return score  

    # ======================================================
    # Demodulation
    # ======================================================
    def demodulate(self, candidates, cyclestart_str):
        out = []
        for c in candidates:
            print(f"Candidate at {c.bounds.f0}Hz")
            bits = self._demodulate_max_power(c)
            if self._check_crc_bits(bits):
                c.demodulated_by = 'Max power'
                c.payload_bits = bits
                out.append(FT8_decode(c, cyclestart_str))
                continue

            bits = self._demodulate_llrldpc(c)
            if self._check_crc_bits(bits):
                c.demodulated_by = "LLR-LDPC"
                c.payload_bits = bits
                out.append(FT8_decode(c, cyclestart_str))

                
        return out

    # ======================================================
    # Internals
    # ======================================================
    def _generate_csync(self):
        """Generate a single 7×7 Costas block mask"""
        costas = [3, 1, 4, 0, 6, 5, 2]
        n = len(costas)
        h = n * self.hops_persymb
        w = n * self.fbins_pertone
        mask = np.full((h, w), -1/(n - 1), np.float32)

        for sym_idx, tone in enumerate(costas):
            t0 = sym_idx * self.hops_persymb
            f0 = tone * self.fbins_pertone
            mask[t0:t0+self.hops_persymb, f0:f0+self.fbins_pertone] = 1.0

        return mask

    def _demodulate_max_power(self, cand: Candidate):
        pgrid = cand.power_grid
        payload_idxs = list(range(7, 36)) + list(range(43, 72))
        symbols = [int(np.argmax(pgrid[i, :])) for i in payload_idxs]
        bits = [b for sym in symbols for b in kGRAY_MAP_TUPLES[sym]]
        return bits

    def _demodulate_llrldpc(self, cand: Candidate):
        LLR174s = []
        payload_idxs = list(range(7, 36)) + list(range(43, 72))
        for sym in payload_idxs:
            t_idx = cand.bounds.t0_idx + sym * self.hops_persymb
            if t_idx >= self.spectrum.complex.shape[0]:
                break
            pwrs = [0.0] * self.sigspec.tones_persymb
            sigma2 = 0.001
            for k in range(self.hops_persymb):
                Z = self.spectrum.complex[t_idx + k, :]
                for i in range(self.sigspec.tones_persymb):
                    f0 = cand.bounds.f0_idx + i * self.fbins_pertone
                    f1 = f0 + self.fbins_pertone
                    pwrs[i] += abs(np.sum(Z[f0:f1])) ** 2
                left = Z[:cand.bounds.f0_idx]
                right = Z[cand.bounds.f0_idx + self.sigspec.tones_persymb*self.fbins_pertone:]
                if left.size + right.size:
                    sigma2 += np.median(np.abs(np.concatenate([left, right])) ** 2)
            pwrs_scaled = [p/sigma2 for p in pwrs]
            for k in range(3):
                s1 = [v for i, v in enumerate(pwrs_scaled) if kGRAY_MAP_TUPLES[i][k]]
                s0 = [v for i, v in enumerate(pwrs_scaled) if not kGRAY_MAP_TUPLES[i][k]]
                m1, m0 = max(s1), max(s0)
                s1v = m1 + math.log(sum(math.exp(v-m1) for v in s1))
                s0v = m0 + math.log(sum(math.exp(v-m0) for v in s0))
                LLR174s.append(s1v - s0v)
        return decode174_91(LLR174s)

    def _check_crc_bits(self, bits):
        """Temporary CRC hook; replace with BitField.crc14_wsjt() later."""
        try:
            import PyFT8.FT8_global_helpers as ghlp
            return ghlp.check_crc(bits)
        except Exception:
            return False
