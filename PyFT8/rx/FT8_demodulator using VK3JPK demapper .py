"""
wave file test
Log to PyFT8.log: 09:47:15.27 (+0.66) Start to Load audio from 210703_133430.wav
Log to PyFT8.log: 09:47:15.65 (+0.38) Start to Find candidates
Log to PyFT8.log: 09:47:15.71 (+0.05) Found 500 candidates
Log to PyFT8.log: 09:47:15.71 (+0.00) Start to deduplicate candidate frequencies
Log to PyFT8.log: 09:47:15.72 (+0.01) Now have 40 candidates
Log to PyFT8.log: 09:47:15.72 (+0.00) Start to sync and demodulate candidates
test     0.000 Rx FT8    +15  0.5 2569 W1FC F5BZB -08 10
test     0.000 Rx FT8    +18  0.2 2154 WM3PEN EA6VQ -09 4
test     0.000 Rx FT8    -07  0.4  721 A92EE F5PSR -14 8
test     0.000 Rx FT8    -12  0.6  588 K1JT HA0DU KN07 11
test     0.000 Rx FT8    -16  0.5  638 N1JFU EA6EE R-07 10
test     0.000 Rx FT8    -17  0.4 1646 K1JT EA3AGB -15 7
Log to PyFT8.log: 09:47:17.09 (+1.37) Start to Show spectrum
Log to PyFT8.log: 09:47:17.41 (+0.31) Start to Show candidates
"""

import math
import numpy as np

from PyFT8.datagrids import Spectrum, Bounds, Candidate
from PyFT8.signaldefs import FT8
from PyFT8.rx.decode174_91 import decode174_91
import PyFT8.FT8_crc as crc
import PyFT8.timers as timers
from PyFT8.comms_hub import config, send_to_ui_ws


class FT8Demodulator:
    def __init__(self, sample_rate=12000, fbins_pertone=3, hops_persymb=5, sigspec=FT8):
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

    def find_candidates(self, topN=1500):
        candidates = []
        for f0_idx in range(self.spectrum.nFreqs - self._csync.shape[1]):
            score = np.sum(np.abs(self.spectrum.complex[: , f0_idx:f0_idx+self._csync.shape[1]]))
            candidates.append(Candidate(self.sigspec, self.spectrum, 0, f0_idx, score))
        candidates.sort(key=lambda c: -c.score)
        return candidates[:topN]

    def deduplicate_candidate_freqs(self, candidates, topN=100):
        min_sep_fbins = 2*self.fbins_pertone
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
    
    def sync_candidate(self, c):
        c.score = -1e10
        for t0_idx in range(self.spectrum.nHops - self.sigspec.num_symbols*self.hops_persymb-1):
            score = self._csync_score_3(t0_idx, c.bounds.f0_idx)
            if(score > c.score):
                c.score = score
                c.update_t0_idx(t0_idx)

    def _csync_score_3(self, t0_idx, f0_idx):
        score = 0.0
        fn_idx = f0_idx + self._csync.shape[1]
        nt = self._csync.shape[0]
        block_hopstarts = [0, 36 * self.hops_persymb, 72 * self.hops_persymb]
        for block_idx in block_hopstarts: 
            t_idx = t0_idx + block_idx
            cgrid = self.spectrum.complex[t_idx:t_idx + nt, f0_idx:fn_idx]
            block_score = np.sum(np.abs(cgrid) * self._csync)
            if block_score > score: score = block_score 
        return score 
        
    # ======================================================
    # Demodulation
    # ======================================================
    def demodulate_candidate(self, candidate, cyclestart_str):
        """ calculate LLRs from c.pgrid (1:1 grid) """
        c = candidate
        LLR174s=[]
        obs = c.power_grid_downsampled
    
        tone_order = 3
        demap_max_symbols = 4
        num_symbols = 2

        demap_max_bits = demap_max_symbols * tone_order
        demap_max_permutations = 1 << demap_max_bits
        demap_one = np.zeros((demap_max_bits, demap_max_permutations), dtype='bool')
        for i in range(demap_max_bits):
            for j in range(demap_max_permutations):
                if j & 1 << i:
                    demap_one[i, j] = True
        demap_not_one = np.logical_not(demap_one)
        
        encoded_bits = 174
        encoded_symbols = encoded_bits // tone_order

        # Gray map and Costas array from WSJT-X lib/ft8/genft8.f90
        gray_map = [0, 1, 3, 2, 5, 6, 4, 7]
        costas = [3, 1, 4, 0, 6, 5, 2]
        costas_offsets = [0, 36, 72]
        costas_order = len(costas)
        costas_symbols = costas_order * len(costas_offsets)

        symbol_offsets = (list(range(costas_order, costas_offsets[1])) +
                          list(range(costas_offsets[1] + costas_order, costas_offsets[2])))
        assert encoded_symbols == len(symbol_offsets)

        total_symbols = encoded_symbols + costas_symbols

        llr = np.empty(encoded_bits) # Storage for Log likelyhood ratios              
        mask = (1 << tone_order) - 1
        num_bits = (num_symbols + 1) * tone_order # Number of bits in a symbol group
        num_permutations = 1 << num_bits # Number of permutations of the bits in a symbol group
        
        # Loop through groups of num_symbol symbols at a time
        for i in range(0, encoded_symbols, num_symbols + 1):
                
            # Sum DFT filter outputs corresponding to all permutations of bits in a symbol group
            s = np.zeros(num_permutations, dtype='complex128')
            for p in range(num_permutations):
                
                # Add up contributions from each symbol in the symbol group for this permutation
                t = p
                for j in range(num_symbols, -1, -1):
                    tone = gray_map[t & mask] # Tone that corresponds to this permutation for this symbol
                    s[p] += obs[symbol_offsets[i] + j, tone] #
                    t >>= tone_order # Prepare for next iteration
            
            # Calculate magnitude of all the sums
            m = np.abs(s)
            
            # Loop through all the bits of the codeword that correspond to this group of symbols
            first_bit = i * tone_order
            last_bit = min(first_bit + num_bits, encoded_bits)
            bit_pos = num_bits - 1 # Most significant bit of the permutations index corresponds with first_bit
            for encoded_bit in range(first_bit, last_bit):               
                # Find maximum magnitude of permutations where this bit position is a 1 and subtract maximum
                # magnitude of permutations where this bit position is a 0
                llr[encoded_bit] = (np.amax(m[demap_one[bit_pos, :num_permutations]]) -
                                    np.amax(m[demap_not_one[bit_pos, :num_permutations]]))
                bit_pos -= 1 # next bit will be less significant than this bit
                          
        # Normalise using standard deviation and scale result with a WSJT-X fudge factor                 
        llr /= np.std(llr)
        llr *= 2.83 # Square root of 8 ???
                                                     
        ncheck, bits, n_its = decode174_91(llr)
        if(ncheck == 0):
            c.demodulated_by = f"LLR-LDPC ({n_its})"
            c.payload_bits = bits
            c.snr = -24 if c.score==0 else int(25*np.log10(c.score/47524936) +18 )
            c.snr = np.clip(c.snr, -24,24).item()
            c.llr = LLR174s
            decode = FT8_decode(c, cyclestart_str)
            if(decode): c.message = decode['decode_dict']['message'] 
            return decode
    
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

def unpack_ft8_g15(g15, ir):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    R = '' if (ir == 0) else 'R'
    return f"{R}{snr:+03d}"


def FT8_decode(signal, cyclestart_str):
    # need to add support for /P and R+report (R-05)
    bits = signal.payload_bits
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
    c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
    ir = int(bits[58])
    g15  = int(''.join(str(b) for b in bits[59:74]), 2)
    if(c28_a + c28_b + g15 == 0):
        return
    call_a = unpack_ft8_c28(c28_a)
    call_b =  unpack_ft8_c28(c28_b)
    grid_rpt = unpack_ft8_g15(g15, ir)
    freq_str = f"{signal.bounds.f0:4.0f}"
    message = f"{call_a} {call_b} {grid_rpt}"
    all_txt_line = f"{cyclestart_str}     0.000 Rx FT8    {signal.snr:+03d} {signal.bounds.t0 :4.1f} {signal.bounds.f0 :4.0f} {message}"
    decode_dict = {'cyclestart_str':cyclestart_str , 'freq':freq_str, 'call_a':call_a,
                 'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':signal.bounds.t0_idx,
                   'dt':f"{signal.bounds.t0 :4.1f}", 'snr':signal.snr, 'priority':False, 'message':message}
    return {'all_txt_line':all_txt_line, 'decode_dict':decode_dict}

