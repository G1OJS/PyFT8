"""
FT8_demodulator.py
------------------
Audio → Spectrum → Candidates → Bits.

Refactored to use new datagrids framework:
    Spectrum / Candidate / Bounds.with_from_physical()
"""

import math
import numpy as np
from scipy.signal import get_window

from PyFT8.datagrids import Spectrum, Bounds, Candidate
from PyFT8.signaldefs import FT8
from PyFT8.rx.ldpc import decode174_91
from PyFT8.rx.FT8_decoder import FT8_decode
from PyFT8.FT8_constants import kGRAY_MAP_TUPLES
# from PyFT8.bitfield import BitField  # later, for CRC


class FT8Demodulator:
    def __init__(self, sample_rate=12000, fbins_pertone=3, hops_persymb=3, spec=FT8):
        # ---- Configuration ----
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.spec = spec

        # ---- Spectrum setup ----
        self.spectrum = Spectrum(
            sample_rate=self.sample_rate,
            fbins_pertone=self.fbins_pertone,
            hops_persymb=self.hops_persymb,
            spec=self.spec
        )

        # ---- FFT precompute ----
        self.FFT_size = self.spectrum.FFT_size
        self._window = get_window("hann", self.FFT_size)
        self._hop_size = int(self.sample_rate / (self.spec.symbols_persec * self.hops_persymb)) 

        # ---- Costas sync mask ----
        self._csync = self._generate_csync()

    # ======================================================
    # Audio → Spectrum
    # ======================================================
    def feed_audio(self, audio: np.ndarray):
        """
        Fill Spectrum.complex from a block of real audio samples.
        """
        nfft = self.FFT_size
        hop = self._hop_size
        nhops = self.spectrum.nHops
        spec = np.zeros((nhops, nfft // 2 + 1), dtype=np.complex64)

        for i in range(nhops):
            s = i * hop
            e = s + nfft
            if e > len(audio):
                break
            frame = audio[s:e] * self._window
            spec[i, :] = np.fft.rfft(frame)

        self.spectrum.complex = spec  # .power is property

    # ======================================================
    # Candidate search
    # ======================================================
    def find_candidates(self, t0=0.0, t1=1.5, f0=100.0, f1=3300.0, topN=50):
        """
        Sweep a time/freq region for Costas sync patterns.
        Returns list of Candidate objects with .score and .best_score set.
        """
        region = Bounds.from_physical(self.spectrum, t0, t1, f0, f1)
        cs_h, cs_w = self._csync.shape
        candidates = []

        for fbin in region.f_range:
            cand = Candidate(self.spectrum, 0, cs_h, fbin, fbin + cs_w)
            for tbin in region.t_range:
                if not region.contains_window(tbin, fbin, (cs_h, cs_w)):
                    continue
                cand.move_to(tbin, fbin)
                cand.score = self._score_at(cand)
            if cand.best_score > 0:
                cand.freq = self.spectrum.freqs[cand.bounds.f0_idx]
                cand.dt = self.spectrum.times[cand.bounds.t0_idx]
                candidates.append(cand.freeze())

        # sort and de-duplicate
        candidates.sort(key=lambda c: -c.best_score)
        uniq = []
        for c in candidates:
            if not any(abs(c.bounds.f0_idx - u.bounds.f0_idx)
                       < 0.5 * self.spec.tones_persymb * self.fbins_pertone
                       for u in uniq):
                uniq.append(c)
        return uniq[:topN]

    # ======================================================
    # Demodulation
    # ======================================================
    def demodulate(self, candidates, cyclestart_str):
        out = []
        for c in candidates:
            bits = self._demodulate_max_power(c)
            if self._check_crc_bits(bits):
                c.demod = "Max power"
                c.payload_bits = bits
                out.append(FT8_decode(c, cyclestart_str))
                continue

            bits = self._demodulate_llrldpc(c)
            if self._check_crc_bits(bits):
                c.demod = "LLR-LDPC"
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


    def _score_at(self, cand: Candidate):
        """Return correlation score of Costas mask at candidate location."""
        t0, f0 = cand.bounds.t0_idx, cand.bounds.f0_idx
        th, fw = self._csync.shape
        t1, f1 = min(t0+th, self.spectrum.nHops), min(f0+fw, self.spectrum.nFreqs)
        blk = np.abs(self.spectrum.complex[t0:t1, f0:f1])
        cs = self._csync[:blk.shape[0], :blk.shape[1]]
        return float(np.sum(cs * blk))

    def _downsample_power(self, cand: Candidate):
        """Reduce fine grid → (num_symbols × tones)."""
        fine = cand.extract_power()
        nsyms, ntones = self.spec.num_symbols, self.spec.tones_persymb
        grid = np.zeros((nsyms, ntones), np.float32)
        for s in range(nsyms):
            t0 = s * self.hops_persymb
            t1 = t0 + self.hops_persymb
            for t in range(ntones):
                f0 = t * self.fbins_pertone
                f1 = f0 + self.fbins_pertone
                grid[s, t] = np.max(fine[t0:t1, f0:f1])
        cand.power_grid = grid
        return grid

    def _demodulate_max_power(self, cand: Candidate):
        grid = self._downsample_power(cand)
        payload_idxs = list(range(7, 36)) + list(range(43, 72))
        symbols = [int(np.argmax(grid[i, :])) for i in payload_idxs]
        bits = [b for sym in symbols for b in kGRAY_MAP_TUPLES[sym]]
        return bits

    def _demodulate_llrldpc(self, cand: Candidate):
        LLR174s = []
        payload_idxs = list(range(7, 36)) + list(range(43, 72))
        for sym in payload_idxs:
            t_idx = cand.bounds.t0_idx + sym * self.hops_persymb
            if t_idx >= self.spectrum.complex.shape[0]:
                break
            pwrs = [0.0] * self.spec.tones_persymb
            sigma2 = 0.001
            for k in range(self.hops_persymb):
                Z = self.spectrum.complex[t_idx + k, :]
                for i in range(self.spec.tones_persymb):
                    f0 = cand.bounds.f0_idx + i * self.fbins_pertone
                    f1 = f0 + self.fbins_pertone
                    pwrs[i] += abs(np.sum(Z[f0:f1])) ** 2
                left = Z[:cand.bounds.f0_idx]
                right = Z[cand.bounds.f0_idx + self.spec.tones_persymb*self.fbins_pertone:]
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
