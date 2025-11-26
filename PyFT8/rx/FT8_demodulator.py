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
from PyFT8.rx.decode174_91_v5_1 import LDPC174_91
import PyFT8.FT8_crc as crc
import PyFT8.timers as timers
from PyFT8.comms_hub import config, send_to_ui_ws

eps = 1e-12

class Spectrum:
    def __init__(self, demodspec):
        self.sigspec = demodspec.sigspec
        self.hops_persymb = demodspec.hops_persymb
        self.fbins_pertone = demodspec.fbins_pertone
        self.max_freq = 3500
        self.audio_start = 0
        self.audio_in = []
        self.dt = demodspec.samples_perhop / demodspec.sample_rate
        self.duplicate_filter = set()
        self.cyclestart_str = 'xxxxxx_xxxxxx'
        self.cycle_epoch = timers.tnow()
        self.FFT_len = int(demodspec.fbins_pertone * demodspec.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = demodspec.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        self.occupancy = None
        self.df = self.max_freq / self.nFreqs
        self.nHops_loaded = 0
        self.hops_percycle = int(demodspec.sample_rate * self.sigspec.cycle_seconds / demodspec.samples_perhop)
        self.fine_grid_complex = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.complex64)
        self.FFT_start_sample_idx = 0
        self.searched = False
        self.candidate_size = (self.sigspec.num_symbols * demodspec.hops_persymb,
                               self.sigspec.tones_persymb * demodspec.fbins_pertone)
        self._csync = np.full((self.sigspec.costas_len, self.candidate_size[1]), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* demodspec.fbins_pertone, (tone+1) * demodspec.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*demodspec.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * demodspec.hops_persymb
        self.candidate_search_after_hop  = (np.max(demodspec.sync_range) + np.max(self.hop_idxs_Costas))
        self.start_decoding_after_hop = (self.sigspec.num_symbols - self.sigspec.costas_len) * demodspec.hops_persymb 

class Candidate:
    def __init__(self, spectrum, sigspec):
        self.size = spectrum.candidate_size
        self.spectrum = spectrum
        self.cycle_epoch = spectrum.cycle_epoch
        self.cyclestart_str = spectrum.cyclestart_str
        self.sigspec = sigspec
        self.origin = None
        self.origin_physical = None
        self.llr = None
        self.llr_std = None
        self.payload_bits = []
        self.decode_dict = None
        self.sent_for_decode = False
        self.time_in_decode = 0
        self.decoded = None
        self.n_its = -1

    @property
    def fine_grid_complex(self):
        c = self
        return self.spectrum.fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0], c.origin[1]:c.origin[1]+c.size[1]].copy()

class FT8Demodulator:
    def __init__(self, max_iters, max_stall, max_ncheck, min_sd, sync_score_thresh):
        self.sigspec = FT8
        self.sample_rate=12000
        self.fbins_pertone=3
        self.hops_persymb=5
        self.sync_score_thresh = sync_score_thresh
        self.min_sd = min_sd
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )
        self.hops_persec = self.sample_rate / self.samples_perhop 
        slack_hops =  int(self.hops_persymb * self.sigspec.symbols_persec * (self.sigspec.cycle_seconds - self.sigspec.num_symbols / self.sigspec.symbols_persec) )
        self.sync_range = range(slack_hops)
        self.ldpc = LDPC174_91(max_iters, max_stall, max_ncheck)

    def find_candidates(self, spectrum, onCandidate_found):
        spectrum.cyclestart_str = timers.cyclestart_str(0)
        spectrum.occupancy = np.zeros(spectrum.nFreqs)
        f0_idxs = range(spectrum.nFreqs - spectrum.candidate_size[1])
        for f0_idx in f0_idxs:
            c = Candidate(spectrum, self.sigspec)
            c.origin = (0, f0_idx)
            c.fine_grid_pwr = np.abs(c.fine_grid_complex)**2
            c.max_pwr = np.max(c.fine_grid_pwr)
            spectrum.occupancy[c.origin[1]:c.origin[1]+c.size[1]] += c.max_pwr
            c.fine_grid_pwr = c.fine_grid_pwr / c.max_pwr
            best = (0, -1e30)
            for h0 in self.sync_range:
                test = (h0, np.sum(c.fine_grid_pwr[h0 + spectrum.hop_idxs_Costas] * spectrum._csync)) 
                if test[1] > best[1]:
                    best = test
            c.score = best[1]
            if(c.score > self.sync_score_thresh):
                c.origin = (best[0], c.origin[1])
                c.origin_physical = spectrum.dt * c.origin[0], spectrum.df * c.origin[1]
                c.last_hop = c.origin[0] + c.size[0]
                c.last_data_hop = c.last_hop - self.sigspec.costas_len * self.hops_persymb
                c.info = f"{c.cyclestart_str} {c.origin} {c.score:5.2f}"
                onCandidate_found(c)
     
    def demodulate_candidate(self, candidate, onResult):
        c = candidate
        t_start_decode = timers.tnow()
        tmp = c.fine_grid_complex.reshape(self.sigspec.num_symbols, self.hops_persymb, self.sigspec.tones_persymb, self.fbins_pertone)
        tmp = tmp[:,0,:,:] 
        tmp = np.abs(tmp)**2
        c.synced_pwr = np.max(tmp)
        c.synced_grid_pwr = tmp[:,:,1]/c.synced_pwr
        c.snr = 10*np.log10(c.synced_pwr)-107
        c.snr = int(np.clip(c.snr, -24,24).item())
        c.llr = []
        E0 = c.synced_grid_pwr[0:78:2]   # potential to speed up as we don't need                    
        E1 = c.synced_grid_pwr[1:79:2]   # to decode costas blocks
        pair_score = E0[:, :, None] * E1[:, None, :]
        ps = pair_score[:, None, :, :]
        V = ps * FT8.block_decode_wt2
        ones  = np.max(V,     where=(FT8.block_decode_wt2 > 0), initial=-np.inf, axis=(2, 3))
        zeros = np.max(-V,    where=(FT8.block_decode_wt2 < 0), initial=-np.inf, axis=(2, 3))
        ones = np.clip(ones,  0.0001, 1e30)
        zeros = np.clip(zeros, 0.0001, 1e30) 
        llr_block = np.log(ones +eps) - np.log(zeros +eps)  
        llr_all = llr_block.reshape(-1)
        for i in range(len(llr_all)):
            if(int(i/3) in FT8.payload_symb_idxs):
                c.llr.extend([llr_all[i]])

        c.llr = c.llr - np.mean(c.llr)
        c.llr_sd = np.std(c.llr)
        c.decoded = False
        if(c.llr_sd > self.min_sd):
            c.llr = 4.5 * c.llr / (c.llr_sd+.001)
            c.payload_bits, c.n_its = self.ldpc.decode(c.llr)
            if(c.payload_bits):
                c.iconf = 0
                decode = FT8_unpack(c)
                if(decode):
                    c.decoded = True
                    decode_dict = decode['decode_dict']
                    key = f"{decode_dict['call_a']} {decode_dict['call_b']} {decode_dict['grid_rpt']}"
                    if(not key in c.spectrum.duplicate_filter):
                        c.spectrum.duplicate_filter.add(key)
                        dt = c.origin_physical[0] + c.spectrum.audio_start - 0.3 -0.5
                        if(dt>7): dt -=15
                        dt = f"{dt:4.1f}"
                        decode_dict.update({'dt': dt})
                        c.message = key
                        c.decode_dict = decode_dict
        c.time_in_decode = timers.tnow() - t_start_decode
        onResult(c)
    
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


def FT8_unpack(signal):
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
    freq_str = f"{signal.origin_physical[1]:4.0f}"
    time_str = f"{signal.origin_physical[0]:4.1f}"
    message = f"{call_a} {call_b} {grid_rpt}"
    all_txt_line = f"{signal.cyclestart_str}     0.000 Rx FT8    {signal.snr:+03d} {time_str} {freq_str} {message}"
    decode_dict = {'cyclestart_str':signal.cyclestart_str , 'freq':freq_str, 'call_a':call_a,
                 'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':signal.origin[0],
                   'dt':time_str, 'snr':signal.snr, 'priority':False, 'message':message}
    return {'all_txt_line':all_txt_line, 'decode_dict':decode_dict}

