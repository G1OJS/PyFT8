import numpy as np
from PyFT8.rx.ldpc import decode174_91
from PyFT8.rx.FT8_decoder import FT8_decode

def crc(bits):
    if(len(bits)<91): return False
    a91=bits[0:91]
    div = [ 1,   1, 0,   0, 1, 1, 1,   0, 1, 0, 1,   0, 1, 1, 1 ]
    code = np.zeros(len(div)-1, dtype=np.int32)
    msg = np.append(a91[0:77], np.zeros(5, dtype=np.int32))
    msg = np.append(msg, code)
    div = np.array(div, dtype=np.int32)
    divlen = len(div)
    for i in range(len(msg)-len(code)):
        if msg[i] == 1:
            msg[i:i+divlen] = np.mod(msg[i:i+divlen] + div, 2)
    return np.array_equal(msg[-len(code):], a91[-14:])

class SpectrumBuffer:
    def __init__(self, nHops, samples_perhop, hop_window, frame_secs, sample_rate):
        self.nHops = nHops
        self.samples_perhop = samples_perhop
        self.hop_window = hop_window
        self.FFT_size = len(self.hop_window)
        self.nFreqs = self.FFT_size // 2 + 1
        self.freqs = np.fft.rfftfreq(self.FFT_size, 1.0 / sample_rate)
        self.times = frame_secs * np.arange(self.nHops) / self.nHops
        self.complex = np.zeros((self.nHops, self.nFreqs), dtype=np.complex64)
        self.power = np.zeros((self.nHops, self.nFreqs), dtype=np.float32)
        self.dB = self.power

    def load_TFGrid(self, audio):
        for hop_idx in range(self.nHops):
            s0 = hop_idx*self.samples_perhop
            if(s0 + self.FFT_size < len(audio)):
                self.complex[hop_idx,:] = np.fft.rfft(audio[s0 : s0 + self.FFT_size] * self.hop_window)
                self.power[hop_idx,:] = np.abs(self.complex[hop_idx,:])**2
                self.dB[hop_idx,:] = 10*np.log10(self.power[hop_idx,:] + 1e-12)

class Signal:
    def __init__(self, hops_persymb, fbins_pertone):
        self.fbin_idx = None
        self.tbin_idx = None
        self.costas_score = -1e9
        self.bits = []
        self.demod = None
        self.freq = None
        self.dt = None
        # passed through only for graphics:
        self.num_symbols = 0
        self.hz_pertone = 0
        self.symbol_secs=0
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        # for debugging:
        self.llr = None
        self.spectrum = None

class FT8Demodulator:
    def __init__(self, sample_rate = 12000, hops_persymb = 3 , fbins_pertone = 3):
        self.sample_rate = sample_rate
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        self.frame_seconds = 15
        self.symbols_persec = 6.25
        self.samples_perhop = int(self.sample_rate / (self.symbols_persec * self.hops_persymb))
        self.FFT_size = int(self.fbins_pertone * self.sample_rate // self.symbols_persec)
        self.hz_pertone = 6.25
        self.num_symbols = 79
        self.costas = [3, 1, 4, 0, 6, 5, 2]
        self.specbuff = SpectrumBuffer(int(self.frame_seconds * self.hops_persymb * self.symbols_persec), self.samples_perhop,
                                       np.kaiser(self.FFT_size,14), self.frame_seconds, self.sample_rate)

    def get_candidates(self, topN=100, t0=0, t1=1.5, f0=100, f1=3300):
        fbin_search_idxs = range(int(np.searchsorted(self.specbuff.freqs, f0)), int(np.searchsorted(self.specbuff.freqs, f1)))
        tbin_search_idxs = range(int(np.searchsorted(self.specbuff.times, t0)), int(np.searchsorted(self.specbuff.times, t1)))
        candidates = []
        for fbin_idx in fbin_search_idxs:
            c = Signal(self.hops_persymb, self.fbins_pertone)
            for tbin_idx in tbin_search_idxs:
                score = max(self._costas_score(tbin_idx, fbin_idx), self._costas_score(36+tbin_idx, fbin_idx), self._costas_score(72+tbin_idx, fbin_idx))
                if(score > c.costas_score):
                    c.costas_score = score
                    c.tbin_idx = tbin_idx
                    c.fbin_idx = fbin_idx
            c.freq = self.specbuff.freqs[c.fbin_idx]
            c.dt = self.specbuff.times[c.tbin_idx]
            c.num_symbols = self.num_symbols
            c.hz_pertone = self.hz_pertone
            c.symbol_secs = 1 / self.symbols_persec
            #for debugging output:
            f0 = max(0, fbin_idx - 2)
            f1 = min(self.specbuff.complex.shape[0], fbin_idx + 2 + 8*self.fbins_pertone)
            t0 = max(0, tbin_idx - 2)
            t1 = min(self.specbuff.complex.shape[1], tbin_idx + 2 + self.hops_persymb*self.num_symbols)
            c.spectrum = self.specbuff.complex[f0:f1, t0:t1]

            if(c.costas_score>0.0): candidates.append(c)
        candidates.sort(key=lambda c: -c.costas_score)

        to_delete = []
        for i, c in enumerate(candidates):
            for j in range(i+1, len(candidates)):
                if(abs(c.freq-candidates[j].freq) < 25):
                    to_delete.append(c if c.costas_score < candidates[j].costas_score else candidates[j]) 
        cands = [c for c in candidates if not c in to_delete]
        return cands[0:topN]

    def demodulate(self, candidates, cyclestart_str):
        output = []
        for c in candidates:
            self._demodulate(c)
            if(crc(c.bits)):
                c.demod = "Max pwr"
                output.append(FT8_decode(c, cyclestart_str))
            else:
                self._demodulate_llrldpc(c)
                if(crc(c.bits)):
                    c.demod = "LLR-LDPC"
                    output.append(FT8_decode(c, cyclestart_str))
        return output
    
    def _costas_score(self, t0_idx, f0_idx):
        score = 0.0
        norm = 0.0
        n_fbins = len(self.costas) * self.fbins_pertone
        for iHop, iCostasTone in enumerate(self.costas):
            t_idx = t0_idx + iHop * self.hops_persymb
            for iFbin in range(n_fbins):
                f_idx = f0_idx + iFbin
                mult = 1 if (int(iFbin/self.fbins_pertone) == iCostasTone) else -1/7
                pwr = self.specbuff.power[t_idx, f_idx]
                norm += pwr
                score += pwr * mult
        return score / norm

    def _demodulate(self, candidate):
        payload_symbols = []
        payload_idxs = list(range(7,36)) + list(range(43,72))
        for sym_idx in payload_idxs:
            t_idx = candidate.tbin_idx + sym_idx * self.hops_persymb
            if t_idx >= self.specbuff.power.shape[0]: break  
            fbin_powers = [0]*8*self.fbins_pertone
            for fbin in range(8*self.fbins_pertone):
                f_idx = candidate.fbin_idx + fbin
                f_idx = np.clip(f_idx, 0, self.specbuff.power.shape[1] - 1)
                fbin_powers[fbin] = self.specbuff.power[t_idx, f_idx]
            payload_symbols.append(int(np.argmax(fbin_powers) / self.fbins_pertone))
        graycode = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
        candidate.bits = [b for sym in payload_symbols for b in graycode[sym]]

    def _demodulate_llrldpc(self, candidate):
        import math
        LLR174s=[]
        payload_idxs = list(range(7,36)) + list(range(43,72))
        for sym_idx in payload_idxs:
            t_idx = candidate.tbin_idx + sym_idx * self.hops_persymb
            if t_idx >= self.specbuff.complex.shape[0]: break
            pwrs = [0.0]*8
            Z = self.specbuff.complex[t_idx, : ]
            for i,p in enumerate(pwrs):
                Zslice = Z[candidate.fbin_idx+ i*self.fbins_pertone:candidate.fbin_idx+(i+1)*self.fbins_pertone]
                pwrs[i] = abs(sum(Zslice))**2

            noise_bins = np.concatenate([Z[:candidate.fbin_idx], Z[candidate.fbin_idx+8*self.fbins_pertone:]])
            sigma2 = .01+np.median(np.abs(noise_bins)**2)

            pwrs_scaled = [p / sigma2 for p in pwrs]
            LLRs = []
            graycode = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
            for k in range(3):
                # use stable log-sum-exp
                s1_vals = [v for i,v in enumerate(pwrs_scaled) if graycode[i][k]==1]
                s0_vals = [v for i,v in enumerate(pwrs_scaled) if graycode[i][k]==0]
                max1 = max(s1_vals)
                max0 = max(s0_vals)
                s1 = max1 + math.log(sum(math.exp(v - max1) for v in s1_vals))
                s0 = max0 + math.log(sum(math.exp(v - max0) for v in s0_vals))
                LLRs.append(s1 - s0)
            LLR174s.extend(LLRs)
        candidate.llr = LLR174s
        candidate.bits = decode174_91(LLR174s)
