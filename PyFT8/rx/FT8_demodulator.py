"""
wave file test 13-11-2025 12:20
Log to PyFT8.log: 12:19:26.70 (+0.02) Start to Load audio from 210703_133430.wav
Log to PyFT8.log: 12:19:27.26 (+0.57) Start to Find candidates
Log to PyFT8.log: 12:19:27.52 (+0.26) Found 1500 candidates
Log to PyFT8.log: 12:19:27.55 (+0.03) Start to deduplicate candidate frequencies
Log to PyFT8.log: 12:19:27.59 (+0.03) Now have 40 candidates
Log to PyFT8.log: 12:19:27.60 (+0.01) Start to sync and demodulate candidates
test     0.000 Rx FT8    +12  0.5 2569 W1FC F5BZB -08 17 None 17 1233
test     0.000 Rx FT8    +15  0.2 2154 WM3PEN EA6VQ -09 7 None 7 1034
test     0.000 Rx FT8    -12  0.4  721 A92EE F5PSR -14 13 None 13 346
test     0.000 Rx FT8    -16  0.6  588 K1JT HA0DU KN07 18 None 18 282
test     0.000 Rx FT8    -22  0.5  640 N1JFU EA6EE R-07 17 None 17 307
test     0.000 Rx FT8    -22  0.4 1646 K1JT EA3AGB -15 12 None 12 790
Log to PyFT8.log: 12:19:28.80 (+1.21) Start to Show spectrum
Log to PyFT8.log: 12:19:29.74 (+0.94) Start to Show candidates
"""

import math
import numpy as np

from PyFT8.datagrids import Spectrum, Candidate
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
        
        # ---- Costas sync mask ----
        nsym = self.sigspec.costas_len
        w    = self.sigspec.tones_persymb * self.fbins_pertone
        # background: uniform negative weight per symbol
        self._csync = np.full((nsym, w), -1/(7*w), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            f0 = tone * self.fbins_pertone + self.fbins_pertone//2
            # positive region = all fine bins in symbol-backbone
            self._csync[sym_idx, f0 - self.fbins_pertone//2 : f0 + (self.fbins_pertone+1)//2] = 1.0

               
    # ======================================================
    # Candidate search and sync
    # ======================================================


    def find_candidates(self, topN=750, score_thresh = 100000):
        nf = self._csync.shape[1]   # number of fine bins covering the 8 tones
        eps = 1e-12
        noise_ratio = 1.0 / nf
        fg = np.abs(self.spectrum.fine_grid_complex)  # [nHops, nFreqs]
        candidates = []
        for f0_idx in range(self.spectrum.nFreqs - nf):
            strip = fg[:, f0_idx:f0_idx + nf]  
            row_sum = strip.sum(axis=1)   
            row_max = strip.max(axis=1) 
            ratio = row_max / (row_sum + eps)
            contrib = row_sum * np.maximum(ratio - noise_ratio, 0.0)
            score = contrib.sum()
            candidates.append(Candidate(FT8, self.spectrum, 0, f0_idx, score))
        candidates.sort(key=lambda c: -c.score)
        candidates = candidates[:topN]
        for i, c in enumerate(candidates):
            c.sort_idx_finder=i
        timers.timedLog(f"Initial search completed")

        filtered_cands = []
        for c in candidates:
            self.sync_candidate(c)
            if(c.score > score_thresh):
                filtered_cands.append(c)
        filtered_cands.sort(key=lambda c: -c.score)
        candidates = filtered_cands
        for i, c in enumerate(candidates):
            c.sort_idx_dedup_sync=i
        return candidates

    def sync_candidate(self, c):
        hp = self.spectrum.hops_persymb
        nsym, w = self._csync.shape
        f0 = c.bounds.f0_idx
        strip = np.abs(self.spectrum.fine_grid_complex[:, f0:f0+w])
        best_score = -1e30
        best_h0 = 0

        for h0 in self.spectrum.sync_hops:
            hop_idxs = h0 + np.arange(nsym) * hp + hp//2
            mask = (hop_idxs >= 0) & (hop_idxs < strip.shape[0])
            if not np.any(mask):
                continue
            window = strip[hop_idxs[mask]]
            score = np.tensordot(window, self._csync[mask])
            if score > best_score:
                best_score = score
                best_h0 = h0
        c.score = best_score
        c.update_bounds(self.spectrum, FT8, self.spectrum.sync_hops[best_h0], f0)


    # ======================================================
    # Demodulation
    # ======================================================

    def demodulate_candidate(self, candidate, cyclestart_str):
        # 2-symbol block decoder
        c = candidate
        decode = False
        iHop = 0
        cspec_4d = c.fine_grid_complex.reshape(FT8.num_symbols, self.hops_persymb, FT8.tones_persymb, self.fbins_pertone)
        while not decode and iHop < self.hops_persymb:
            c.llr = []
            cspec = 0.2*cspec_4d[:,iHop,:,0]+ cspec_4d[:,iHop,:,1] + 0.2*cspec_4d[:,iHop,:,2]
            power_per_tone_per_symbol = (np.abs(cspec)**2)
            E0 = power_per_tone_per_symbol[0:78:2]                        
            E1 = power_per_tone_per_symbol[1:79:2]
            pair_score = E0[:, :, None] * E1[:, None, :]
            ps = pair_score[:, None, :, :]
            V = ps * FT8.block_decode_wt2
            ones  = np.max(V,     where=(FT8.block_decode_wt2 > 0), initial=-np.inf, axis=(2, 3))
            zeros = np.max(-V,    where=(FT8.block_decode_wt2 < 0), initial=-np.inf, axis=(2, 3))
            llr_block = np.log(ones ) - np.log(zeros )  
            llr_all = llr_block.reshape(-1)
            for i in range(len(llr_all)):
                if(int(i/3) in FT8.payload_symb_idxs):
                    c.llr.extend([llr_all[i]])
            c.llr = 3 * (c.llr - np.mean(c.llr)) / np.std(c.llr)
            ncheck, c.payload_bits, n_its = decode174_91(c.llr)
            if(ncheck == 0):
                c.iHop = iHop
                c.snr = -24 if c.score==0 else int(25*np.log10(c.score/47524936) +18 )
                c.snr = np.clip(c.snr, -24,24).item()
                decode = FT8_decode(c, cyclestart_str)
                if(decode):
                    c.message = decode['decode_dict']['message'] 
                return decode
            iHop +=1
    
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

