import numpy as np

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
        self.symbols = None
        self.bits = None
        self.freq = None
        self.dt = None
        # passed through only for graphics:
        self.num_symbols = 0
        self.hz_pertone = 0
        self.symbol_secs=0
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone

class FT8Demodulator:
    def __init__(self, sample_rate = 12000, hops_persymb =4 , fbins_pertone = 1):
        self.sample_rate = sample_rate
        self.hops_persymb = hops_persymb
        self.fbins_pertone = fbins_pertone
        self.frame_seconds = 15
        self.symbols_persec = 6.25
        self.samples_perhop = int(self.sample_rate / (self.symbols_persec * self.hops_persymb))
        self.FFT_size = int(self.sample_rate // self.symbols_persec)
        self.hz_pertone = 6.25
        self.num_symbols = 79
        self.costas = [3, 1, 4, 0, 6, 5, 2]
        self.specbuff = SpectrumBuffer(int(self.frame_seconds * self.hops_persymb * self.symbols_persec), self.samples_perhop,
                                       np.hanning(self.FFT_size), self.frame_seconds, self.sample_rate)

    def get_candidates(self, topN=100, t0=0, t1=1.5, f0=100, f1=4000):
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
            if(c.costas_score>0): candidates.append(c)
        candidates.sort(key=lambda c: -c.costas_score)

        to_delete = []
        for i, c in enumerate(candidates):
            for j in range(i+1, len(candidates)):
                if(abs(c.freq-candidates[j].freq) < 25):
                    to_delete.append(c if c.costas_score < candidates[j].costas_score else candidates[j]) 
        cands = [c for c in candidates if not c in to_delete]
        return cands[0:topN]

    def demodulate(self, candidates):
        for c in candidates:
            self._demodulate(c)
        return candidates
    
    def _costas_score(self, t0_idx, f0_idx):
        score = 0.0
        f_idxs = range(f0_idx, f0_idx + len(self.costas) * self.fbins_pertone)
        for i, tone in enumerate(self.costas):
            t_idx = t0_idx + i * self.hops_persymb
            for j, f_idx in enumerate(f_idxs):
                mult = 1 if (int(j/self.fbins_pertone) == tone) else -1/7
                pwr = self.specbuff.power[t_idx, f_idx]
                score += pwr * mult
        return score

    def _demodulate(self, candidate):
        candidate.symbols = [0] * self.num_symbols
        for sym_idx in range(self.num_symbols):
            t_idx = candidate.tbin_idx + sym_idx * self.hops_persymb
            if t_idx >= self.specbuff.power.shape[0]: break  
            tone_powers = [0]*8
            for tone in range(8):
                f_idx = int(round(candidate.fbin_idx + tone * self.fbins_pertone))
                f_idx = np.clip(f_idx, 0, self.specbuff.power.shape[1] - 1)
                tone_powers[tone] = self.specbuff.power[t_idx, f_idx]
            candidate.symbols[sym_idx] = int(np.argmax(tone_powers))





