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
from PyFT8.rx.decode174_91_v5_2 import LDPC174_91
import PyFT8.FT8_crc as crc
#import PyFT8.timers as timers
from PyFT8.comms_hub import config, send_to_ui_ws
import threading
import PyFT8.timers as timers

eps = 1e-12

class Spectrum:
    def __init__(self, demodspec):
        self.sigspec = demodspec.sigspec
        self.hops_persymb = demodspec.hops_persymb
        self.fbins_pertone = demodspec.fbins_pertone
        self.max_freq = 3500 
        self.dt = demodspec.samples_perhop / demodspec.sample_rate
        self.FFT_len = int(demodspec.fbins_pertone * demodspec.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = demodspec.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        self.df = self.max_freq / self.nFreqs
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * demodspec.hops_persymb)
        self.candidate_size = (self.sigspec.num_symbols * demodspec.hops_persymb,
                               self.sigspec.tones_persymb * demodspec.fbins_pertone)
        self._csync = np.full((self.sigspec.costas_len, self.candidate_size[1]), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* demodspec.fbins_pertone, (tone+1) * demodspec.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*demodspec.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * demodspec.hops_persymb
        self.candidate_search_after_hop  = (np.max(demodspec.sync_range) + np.max(self.hop_idxs_Costas)) +1
        self.fine_grid_complex = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.complex64)
        self.sync_search_band = self.fine_grid_complex[:self.candidate_search_after_hop,:] # move to _init_?
        self.occupancy = np.zeros(self.nFreqs)
        self.reset(0)
        self.__isfrozen = True
        
    def reset(self, cycle_start_offset): #(is this really a new class called 'cycle'?)
        self.searched = False
        self.nHops_loaded = 0
        self.audio_in = []
        self.duplicate_filter = set()
        self.cycle_start_offset = cycle_start_offset

class Candidate:
    next_id = 0
    def __init__(self, spectrum, lifetime):
        self.id = Candidate.next_id
        Candidate.next_id +=1
        self.sigspec = spectrum.sigspec
        self.size = spectrum.candidate_size
        self.cyclestart_str = timers.cyclestart_str()
        self.expiry_time = timers.tnow() + lifetime
        self.sync_result = None
        self.synced_grid_complex = None
        self.demap_requested = False
        self.demap_result = None
        self.ldpc_requested = False
        self.ldpc_result = None
        self.decode_result = None
        self.timings = stats = { 't_requested_demap': None, 't_end_demap': None,
                                 't_requested_ldpc': None, 't_end_ldpc': None,}
        self.__isfrozen = True

    @property
    def decode_success(self):
        return not (self.decode_result == None)

    @property
    def message(self):
        c = self
        return f"{c.decode_result['call_a']} {c.decode_result['call_b']} {c.decode_result['grid_rpt']}"

    @property
    def metrics(self):
        return {
            "cand_id": self.id,
            "decode_success": int(self.decode_success),
            "sync_score": self.sync_result['sync_score'],
            "snr": self.demap_result['snr'],
            "llr_sd": self.demap_result['llr_sd'],
            "ldpc_iters": self.ldpc_result['n_its']
        }

class FT8Demodulator:
    def __init__(self, sigspec, max_iters, max_stall, max_ncheck):
        self.sigspec = sigspec
        self.sample_rate=12000
        self.fbins_pertone=3
        self.hops_persymb=5
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hops_per_costas_block = self.hops_persymb * self.sigspec.costas_len
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )
        self.hops_persec = self.sample_rate / self.samples_perhop 
        slack_hops =  int(self.hops_persymb * (self.sigspec.symbols_persec * self.sigspec.cycle_seconds - self.sigspec.num_symbols))
        self.sync_range = range(slack_hops)
        self.ldpc = LDPC174_91(max_iters, max_stall, max_ncheck)

    def find_syncs(self, spectrum, sync_score_thresh, onSync):
        f0_idxs = range(spectrum.nFreqs - spectrum.candidate_size[1])
        for f0_idx in f0_idxs:
            fine_grid_complex = spectrum.sync_search_band[:, f0_idx:f0_idx + self.fbins_per_signal]
            fine_grid_pwr = np.abs(fine_grid_complex)**2
            max_pwr = np.max(fine_grid_pwr)
            spectrum.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            fine_grid_pwr = fine_grid_pwr / max_pwr
            best = (0, -1e30)
            for h0 in self.sync_range:
                test = (h0, float(np.dot(fine_grid_pwr[h0 + spectrum.hop_idxs_Costas].ravel(), spectrum._csync.ravel())))
                if test[1] > best[1]:
                    best = test
            if(best[1] > sync_score_thresh):
                sync_result = {'sync_score': best[1], 
                                  'origin': (best[0], f0_idx, spectrum.dt * best[0], spectrum.df * (f0_idx + 1)),
                                  'last_hop': best[0] + spectrum.candidate_size[0],
                                  'last_data_hop': best[0] + spectrum.candidate_size[0],
                                  'first_data_hop': best[0] + self.hops_per_costas_block}
                onSync(sync_result)

    def demap_candidate(self, spectrum, candidate):
        c = candidate
        origin = c.sync_result['origin']
        synced_grid_complex = c.synced_grid_complex.reshape(self.sigspec.num_symbols, self.hops_persymb,
                                                          self.sigspec.tones_persymb, self.fbins_pertone)
        synced_grid_complex = synced_grid_complex[:,0,:,:] # first hop of self.hops_persymb = the one we synced to
        synced_grid_pwr = np.abs(synced_grid_complex)**2
        synced_pwr = np.max(synced_grid_pwr)
        llr = []
        synced_grid_pwr_central = synced_grid_pwr[:,:,1]/synced_pwr # centre frequency bin
        snr = 10*np.log10(synced_pwr)-107
        snr = int(np.clip(snr, -24,24).item())
        E0 = synced_grid_pwr_central[0:78:2]   # potential to speed up as we don't need                    
        E1 = synced_grid_pwr_central[1:79:2]   # to decode costas blocks
        pair_score = E0[:, :, None] * E1[:, None, :]
        ps = pair_score[:, None, :, :]
        wts = spectrum.sigspec.block_decode_wt2
        V = ps * wts
        ones  = np.max(V,     where=(wts > 0), initial=-np.inf, axis=(2, 3))
        zeros = np.max(-V,    where=(wts < 0), initial=-np.inf, axis=(2, 3))
        ones = np.clip(ones,  0.0001, 1e30)
        zeros = np.clip(zeros, 0.0001, 1e30) 
        llr_block = np.log(ones) - np.log(zeros)  
        llr_all = llr_block.reshape(-1)
        for i in range(len(llr_all)):
            if(int(i/3) in spectrum.sigspec.payload_symb_idxs):
                llr.extend([llr_all[i]])
        llr = llr - np.mean(llr)
        llr_sd = np.std(llr)
        c.demap_result = {'llr_sd':llr_sd,
                          'llr':llr,
                          'snr':snr}

    def decode_candidate(self, candidate, onDecode):
        c = candidate
        llr = 3 * c.demap_result['llr'] / (c.demap_result['llr_sd']+.001)
        c.ldpc_result = self.ldpc.decode(candidate)
        if(c.ldpc_result['payload_bits']):
            c.decode_result = FT8_unpack(c)
        onDecode(c)
    
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

def FT8_unpack(c):
    # need to add support for /P and R+report (R-05)
    bits = c.ldpc_result['payload_bits']
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
    c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
    ir = int(bits[58])
    g15  = int(''.join(str(b) for b in bits[59:74]), 2)
    if(c28_a + c28_b + g15 == 0):
        return None
    call_a = unpack_ft8_c28(c28_a)
    call_b =  unpack_ft8_c28(c28_b)
    grid_rpt = unpack_ft8_g15(g15, ir)
    origin = c.sync_result['origin']
    snr = c.demap_result['snr']
    freq_str = f"{origin[3]:4.0f}"
    time_str = f"{origin[2]:4.1f}"
    decode = {'cyclestart_str':c.cyclestart_str , 'freq':freq_str, 'call_a':call_a,
              'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':origin[0],
              'dt':time_str, 'snr':snr}
    return decode

