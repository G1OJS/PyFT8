"""
wave file tests

13-11-2025 12:20
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

19-11-2025 15:32
  Tload+  Rx call  Tx call     GrRp  SyncScr      snr       t0      cfg       f0  sch_idx    iters 
    1.23    N1JFU    EA6EE     R-07    9.431       22       11        0      306        0        9
    1.32        -        -        -    8.062       16       11        0      307        1        4
    1.37   WM3PEN    EA6VQ      -09    7.974       15        5        0     1034        2        0
    1.39        -        -        -    7.552       13        5        0     1035        3        0
    1.42     W1FC    F5BZB      -08    4.441       -9       11        0     1233        8        0
    1.50        -        -        -    4.093      -13        5        0     1036        9        4
    2.12        -        -        -    3.072      -24       11        0     1234       25        0
    2.55     K1JT   EA3AGB      -15    2.173      -24        8        0      790       76       16
    4.07     K1JT    HA0DU     KN07    1.465      -24       12        0      282      264        6
    4.26    A92EE    F5PSR      -14    1.428      -24        9        0      345      281        7
    4.30 DONE. Unique decodes = 6

"""

import math
import numpy as np
from PyFT8.signaldefs import FT8
from PyFT8.rx.decode174_91 import decode174_91
import PyFT8.FT8_crc as crc
import PyFT8.timers as timers
from PyFT8.comms_hub import config, send_to_ui_ws

eps = 1e-12

class Spectrum:
    def __init__(self, sample_rate, fbins_pertone, hops_persymb, sigspec):
        self.max_freq = 3500
        self.sample_rate = float(sample_rate)
        self.sigspec = sigspec
        self.fbins_pertone = int(fbins_pertone)
        self.hops_persymb = int(hops_persymb)
        self.FFT_len = int(self.fbins_pertone * self.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = self.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        
    def fill_arrays(self, fine_grid_complex):
        self.fine_grid_complex = fine_grid_complex
        self.nHops_loaded = self.fine_grid_complex.shape[0]
        self.hop0_window_size = self.nHops_loaded - (self.sigspec.num_symbols + self.sigspec.costas_len) * self.hops_persymb
        self.search_band_hops = self.hop0_window_size + self.sigspec.costas_len * self.hops_persymb
        self.extent = [0, self.max_freq, 0,  (self.nHops_loaded / self.hops_persymb) / self.sigspec.symbols_persec ]
        self.df = self.extent[1]/self.fine_grid_complex.shape[1]
        self.dt = self.extent[3]/self.fine_grid_complex.shape[0]
        
class Candidate:
    def __init__(self, spectrum, f0_idx, size, cyclestart_str):
        self.size = size
        self.origin = (0, f0_idx)
        self.spectrum = spectrum
        self.cyclestart_str = cyclestart_str

    def prep_for_decode(self, sigspec, t0):
        self.origin = (t0, self.origin[1])
        self.llr = None
        self.llr_std = None
        self.payload_bits = None
        self.sigspec = sigspec  
        self.payload_bits = []
        self.message = None
        self.snr = -24
        self.origin_physical = (self.spectrum.dt * self.origin[0], self.spectrum.df * self.origin[1])
        self.fine_grid_complex = self.spectrum.fine_grid_complex[self.origin[0]:self.origin[0] + self.size[0],:][:, self.origin[1]:self.origin[1] + self.size[1]] 

class FT8Demodulator:
    def __init__(self):
        sample_rate=12000
        fbins_pertone=3
        hops_persymb=3
        sigspec=FT8
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec
        self.spectrum = Spectrum( fbins_pertone=self.fbins_pertone, hops_persymb=self.hops_persymb,
                                  sample_rate=self.sample_rate, sigspec=self.sigspec)
        self.candidate_size = (self.sigspec.num_symbols * self.hops_persymb,
                               self.sigspec.tones_persymb * self.fbins_pertone)
        # ---- Costas sync mask ---- nsym(7) x nfBins(7 * self.fbins_pertone)
        nsym = self.sigspec.costas_len
        self._csync = np.full((nsym, self.candidate_size[1]), -1/(nsym-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, 7*self.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(nsym) * self.spectrum.hops_persymb
     
    def load_audio(self, audio_in):
        nSamps = len(audio_in)
        nHops_loaded = int(self.hops_persymb * self.sigspec.symbols_persec * (nSamps-self.spectrum.FFT_len)/self.sample_rate)
        fine_grid_complex = np.zeros((nHops_loaded, self.spectrum.nFreqs), dtype = np.complex64)
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )                                   
        for hop_idx in range(nHops_loaded):
            sample_idx = int(hop_idx * self.samples_perhop)
            aud = audio_in[sample_idx:sample_idx + self.spectrum.FFT_len] * np.kaiser(self.spectrum.FFT_len, 14)
            fine_grid_complex[hop_idx,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
        self.spectrum.fill_arrays(fine_grid_complex)
        timers.timedLog(f"[load_audio] Loaded {nHops_loaded} hops ({nHops_loaded*0.16/self.hops_persymb:.2f}s)")

    def find_candidates(self, cyclestart_str = 'xxxxxx_xxxxxx',  silent = False, prioritise_Hz = False):
        candidates = []
        output_limit = int(config.decoder_search_limit) 
        f0_idxs = range(self.spectrum.nFreqs - self.candidate_size[1])
        for f0_idx in f0_idxs:
            c = Candidate(self.spectrum, f0_idx, self.candidate_size, cyclestart_str)
            fc = self.spectrum.fine_grid_complex[:,f0_idx:f0_idx + c.size[1]]
            c.fine_grid_pwr = np.abs(fc)**2
            c.max_pwr = np.max(c.fine_grid_pwr)
            c.fine_grid_pwr = c.fine_grid_pwr / c.max_pwr
            best = (0, -1e30)
            for h0 in range(self.spectrum.hop0_window_size):
                window = c.fine_grid_pwr[h0 + self.hop_idxs_Costas]
                test = (h0, np.sum(window * self._csync)) 
                if test[1] > best[1]:
                    best = test
            c.score = best[1]
            if(c.score > .5):
                # if there's an existing neighbour in frequency, replace it if we have a better score, otherwise don't append us 
                neighbour_lf = [n for n in candidates if (c.origin[1] - n.origin[1] <=2)]
                if(neighbour_lf):
                    if(neighbour_lf[0].score >= c.score): continue
                    if(neighbour_lf[0].score < c.score): candidates.remove(neighbour_lf[0])
                c.prep_for_decode(FT8, best[0])
                
                candidates.append(c)
                if(prioritise_Hz and abs(c.origin_physical[1]-prioritise_Hz) < 1):
                    c.score = 10
        candidates.sort(key=lambda c: -c.score)
        candidates = candidates[:output_limit]
        for i, c in enumerate(candidates):
            c.sort_idx = i
        timers.timedLog(f"[find_candidates] Sync completed with {len(candidates)} candidates", silent = False)
        return candidates

    def demodulate_candidate(self, candidate, silent = False):
        c = candidate 
        decode = False
        iconf = 0
        cspec_4d = c.fine_grid_complex.reshape(FT8.num_symbols, self.hops_persymb, FT8.tones_persymb, self.fbins_pertone)
        c.llr = []
        cspec = cspec_4d[:,0,:,1]
        power_per_tone_per_symbol = (np.abs(cspec)**2)
        E0 = power_per_tone_per_symbol[0:78:2]                        
        E1 = power_per_tone_per_symbol[1:79:2]
        pair_score = E0[:, :, None] * E1[:, None, :]
        ps = pair_score[:, None, :, :]
        V = ps * FT8.block_decode_wt2
        ones  = np.max(V,     where=(FT8.block_decode_wt2 > 0), initial=-np.inf, axis=(2, 3))
        zeros = np.max(-V,    where=(FT8.block_decode_wt2 < 0), initial=-np.inf, axis=(2, 3))
        ones = np.clip(ones,  0.0001, 1e30)
        zeros = np.clip(zeros, 0.0001, 1e30) 
        llr_block = np.log(ones ) - np.log(zeros )  
        llr_all = llr_block.reshape(-1)
        for i in range(len(llr_all)):
            if(int(i/3) in FT8.payload_symb_idxs):
                c.llr.extend([llr_all[i]])
        c.llr = 3 * (c.llr - np.mean(c.llr)) / np.std(c.llr)
        ncheck, bits, n_its = decode174_91(c.llr)
        if(ncheck == 0):
            c.payload_bits = bits
            c.snr = -24 if c.score==0 else int(10+100*np.log10(c.score/7))
            c.snr = np.clip(c.snr, -24,24).item()
            c.n_its = n_its
            decode = FT8_decode(c)
            if(decode):
                c.iconf = iconf
                c.message = decode['decode_dict']['message']
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


def FT8_decode(signal):
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
    freq_str = f"{signal.origin[1]*signal.spectrum.df:4.0f}"
    time_str = f"{signal.origin[0]*signal.spectrum.dt:4.1f}"
    message = f"{call_a} {call_b} {grid_rpt}"
    all_txt_line = f"{signal.cyclestart_str}     0.000 Rx FT8    {signal.snr:+03d} {time_str} {freq_str} {message}"
    decode_dict = {'cyclestart_str':signal.cyclestart_str , 'freq':freq_str, 'call_a':call_a,
                 'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':signal.origin[0],
                   'dt':time_str, 'snr':signal.snr, 'priority':False, 'message':message}
    return {'all_txt_line':all_txt_line, 'decode_dict':decode_dict}

