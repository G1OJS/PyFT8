import numpy as np
from PyFT8.rx.ldpc import decode174_91
from PyFT8.rx.FT8_decoder import FT8_decode
from PyFT8.FT8_constants import kGRAY_MAP_TUPLES
import PyFT8.FT8_global_helpers as ghlp

class SpectrumBuffer:
    def __init__(self, nHops = 0, length_secs = 0, nFreqs = 0, width_Hz = 0):
        self.length_secs = length_secs
        self.width_Hz = width_Hz
        self.nHops = nHops
        self.nFreqs = nFreqs
        self.freqs = self.width_Hz * np.arange(self.nFreqs) / (self.nFreqs -1)
        self.times = self.length_secs * np.arange(self.nHops) / (self.nHops -1)
        self.complex = np.zeros((self.nHops, self.nFreqs), dtype=np.complex64)+1
        self.power = np.zeros((self.nHops, self.nFreqs), dtype=np.float32)+1

class Signal:
    def __init__(self, num_symbols =79, tones_persymb = 8, symbols_persec = 6.25):
        self.fbin_idx = None
        self.tbin_idx = None
        self.search_score = -1e9
        self.num_symbols = num_symbols
        self.symbols_persec = symbols_persec
        self.tones_persymb = tones_persymb 
        self.power_grid = np.zeros((self.num_symbols, self.tones_persymb), dtype=np.float32)
        self.llr = None
        self.payload_symbol_idxs = list(range(7,36)) + list(range(43,72))
        self.payload_symbols=[]
        self.payload_bits = []
        self.freq = None
        self.dt = None
        self.demod = None

class FT8Demodulator:
    def __init__(self, sample_rate = 12000, hops_persymb = 3 , fbins_pertone = 3):
        self.frame_secs = 15 # move to signal class
        self.sample_rate = sample_rate
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        self.symbols_persec = 6.25 # move to signal class
        self.tones_persymb = 8 # move to signal class
        self.FFT_size = int(self.fbins_pertone * self.sample_rate // self.symbols_persec)
        self.num_symbols = 79 # move to signal class
        self.costas = [3, 1, 4, 0, 6, 5, 2] # move to signal class
        self.csync = self._generate_csync() # move to signal class
        self.specbuff = SpectrumBuffer(nHops        = int(self.hops_persymb * self.symbols_persec * self.frame_secs),
                                       length_secs  = self.frame_secs,
                                       nFreqs       = self.FFT_size // 2 + 1,
                                       width_Hz     = self.sample_rate/2)

    def _generate_csync(self): # move to signal class
        csync_len = len(self.costas)*self.hops_persymb
        csync_wid = len(self.costas)*self.fbins_pertone
        csync = np.zeros((csync_len, csync_wid), dtype=np.int16)
        for t_idx in range(csync_len):
          for f_idx in range(csync_wid):
            symb_idx = int(t_idx / self.hops_persymb)
            tone_idx = int(f_idx / self.fbins_pertone)
            csync[t_idx, f_idx] = 1 if tone_idx == self.costas[symb_idx] else -1/(len(self.costas)-1)
        return csync
    
    def load(self, audio):
        for hop_idx in range(self.specbuff.nHops):
            samp_idx = int(hop_idx * self.sample_rate / (self.symbols_persec * self.hops_persymb))
            if(samp_idx + self.FFT_size < len(audio)):
                self.specbuff.complex[hop_idx,:] = np.fft.rfft(audio[samp_idx : samp_idx + self.FFT_size] * np.kaiser(self.FFT_size,14))
                
    def _get_search_score(self, t0_idx, f0_idx):
        score = 0.0
        for symb_idx in [0, 36, 72]:
            t_idx = t0_idx + symb_idx * self.hops_persymb
            block_score = np.sum(self.csync * np.abs(self.specbuff.complex[t_idx:t_idx + self.csync.shape[0], f0_idx:f0_idx + self.csync.shape[1]]))
            #score = block_score if block_score > score else score
            score += block_score
        return score

    def _get_downsampled_power(self, candidate):
        for specbuff_t_idx in range(candidate.tbin_idx, candidate.tbin_idx+candidate.num_symbols*self.hops_persymb):
            for specbuff_f_idx in range(candidate.fbin_idx, candidate.fbin_idx + candidate.tones_persymb * self.fbins_pertone):
                candidate_t_idx = int((specbuff_t_idx - candidate.tbin_idx) / self.hops_persymb)
                candidate_f_idx = int((specbuff_f_idx - candidate.fbin_idx) / self.fbins_pertone)
                candidate.power_grid[candidate_t_idx, candidate_f_idx] += self.specbuff.power[specbuff_t_idx, specbuff_f_idx]
        
    def get_candidates(self, topN=100, t0=0, t1=1.5, f0=100, f1=3300):
        self.specbuff.power = np.abs(self.specbuff.complex)**2 # precalculate to avoid recalc during search
        fbin_search_idxs = range(int(np.searchsorted(self.specbuff.freqs, f0)), int(np.searchsorted(self.specbuff.freqs, f1)))
        tbin_search_idxs = range(int(np.searchsorted(self.specbuff.times, t0)), int(np.searchsorted(self.specbuff.times, t1)))
        candidates = []
        for fbin_idx in fbin_search_idxs:
            c = Signal(self.num_symbols, self.tones_persymb, self.symbols_persec)
            for tbin_idx in tbin_search_idxs:
                score = self._get_search_score(tbin_idx, fbin_idx)
                if(score > c.search_score):
                    c.search_score, c.tbin_idx, c.fbin_idx = score, tbin_idx, fbin_idx 
            if(c.search_score>0):
                candidates.append(c)
                
        candidates.sort(key=lambda c: -c.search_score)
        to_delete = []
        for c1_idx, c1 in enumerate(candidates):
            for c2_idx in range(c1_idx+1, len(candidates)):
                c2 = candidates[c2_idx]
                if(abs(c1.fbin_idx - c2.fbin_idx) < 0.5 * c.tones_persymb * self.fbins_pertone):
                    to_delete.append(c1 if c1.search_score < c2.search_score else c2) 
        cands = [c for c in candidates if not c in to_delete][0:topN]
        for c in cands:
            self._get_downsampled_power(c)
            c.freq = self.specbuff.freqs[c.fbin_idx]
            c.dt = self.specbuff.times[c.tbin_idx]
        return cands

    def demodulate(self, candidates, cyclestart_str):
        output = []
        for c in candidates:
            self._demodulate(c)
            if(ghlp.check_crc(c.payload_bits)):
                c.demod = "Max pwr"
                output.append(FT8_decode(c, cyclestart_str))
             #   print(c.fbin_idx, c.freq, c.tbin_idx, c.dt)
             #   print(c.bits)
            else:
                self._demodulate_llrldpc(c)
                if(ghlp.check_crc(c.payload_bits)):
                    c.demod = "LLR-LDPC"
                    output.append(FT8_decode(c, cyclestart_str))

        return output

    def _demodulate(self, candidate):
        for sym_idx in candidate.payload_symbol_idxs:
            tone_powers = candidate.power_grid[sym_idx, :]
            candidate.payload_symbols.append(np.argmax(tone_powers))
        candidate.payload_bits = [b for sym in candidate.payload_symbols for b in kGRAY_MAP_TUPLES[sym]]

    def _demodulate_llrldpc(self, candidate):
        import math
        LLR174s=[]
        payload_symbol_idxs = list(range(7,36)) + list(range(43,72))
        for sym_idx in payload_symbol_idxs:
            t_idx = candidate.tbin_idx + sym_idx * self.hops_persymb
            if t_idx >= self.specbuff.complex.shape[0]: break
            pwrs = [0.0]*8
            sigma2 = 0.001
            for k in range(self.hops_persymb):
                Z = self.specbuff.complex[t_idx+k, : ]
                for i,p in enumerate(pwrs):
                    Zslice = Z[candidate.fbin_idx+ i*self.fbins_pertone:candidate.fbin_idx+(i+1)*self.fbins_pertone]
                    pwrs[i] += abs(sum(Zslice))**2
                noise_bins = np.concatenate([Z[:candidate.fbin_idx], Z[candidate.fbin_idx+8*self.fbins_pertone:]])
                sigma2 += np.median(np.abs(noise_bins)**2)
            pwrs_scaled = [p / sigma2 for p in pwrs]
            LLRs = []
            
            for k in range(3):
                s1_vals = [v for i,v in enumerate(pwrs_scaled) if kGRAY_MAP_TUPLES[i][k]==1]
                s0_vals = [v for i,v in enumerate(pwrs_scaled) if kGRAY_MAP_TUPLES[i][k]==0]
                max1 = max(s1_vals)
                max0 = max(s0_vals)
                s1 = max1 + math.log(sum(math.exp(v - max1) for v in s1_vals))
                s0 = max0 + math.log(sum(math.exp(v - max0) for v in s0_vals))
                LLRs.append(s1 - s0)
            LLR174s.extend(LLRs)
        candidate.llr = LLR174s
        candidate.payload_bits = decode174_91(LLR174s)
