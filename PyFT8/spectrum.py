
import numpy as np
import time
from PyFT8.audio import find_device, AudioIn
from PyFT8.candidate import Candidate

class Spectrum:
    def __init__(self, sigspec, sample_rate, max_freq, hops_persymb, fbins_pertone):
        self.sigspec = sigspec
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.max_freq = max_freq
        self.hops_persymb = hops_persymb
        self.audio_in = AudioIn(self.sigspec.cycle_seconds, self.sigspec.symbols_persec, hops_persymb, fbins_pertone, max_freq)
        self.nFreqs = self.audio_in.nFreqs
        self.dt = 1.0 / (self.sigspec.symbols_persec * self.hops_persymb) 
        self.df = max_freq / (self.nFreqs -1)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb
        self.hop_start_lattitude = int(0.5 + (15 - (79-7)*0.16) / self.dt)
        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self.h_search = self.hop_start_lattitude + self.nhops_costas  + 36 * self.hops_persymb
        self.h_demap = self.sigspec.payload_symb_idxs[-1] * self.hops_persymb
        self.occupancy = np.zeros(self.nFreqs)
        self.csync_flat = self.make_csync(sigspec)

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -1/(self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def get_syncs(self, f0_idx, pnorm):
        syncs = []
        hps, bpt = self.hops_persymb, self.fbins_pertone
        hop_idxs_Costas =  np.arange(7) * hps
        for search_params in [(range(0, self.hop_start_lattitude), 0),
                              (range((36-7) * hps, 36 * hps + self.hop_start_lattitude), -36 * hps)]:
            best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
            for h0_idx in search_params[0]:
                sync_score = float(np.dot(pnorm[h0_idx + hop_idxs_Costas ,  :].ravel(), self.csync_flat))
                test_sync = {'h0_idx':h0_idx + search_params[1], 'score':sync_score, 'dt': h0_idx * self.dt - 0.7}
                if test_sync['score'] > best_sync['score']:
                    best_sync = test_sync
            syncs.append(best_sync)
        return syncs

    def search(self, f0_idxs, cyclestart_str):
        cands = []
        pgrid = self.audio_in.pgrid_main[:self.h_search,:]
        for f0_idx in f0_idxs:
            p = pgrid[:, f0_idx:f0_idx + self.fbins_per_signal]
            max_pwr = np.max(p)
            pnorm = p / max_pwr
            self.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            c = Candidate()
            c.f0_idx = f0_idx
            c.syncs = self.get_syncs(f0_idx, pnorm)
            hps, bpt = self.hops_persymb, self.fbins_pertone
            c.freq_idxs = [c.f0_idx + bpt // 2 + bpt * t for t in range(self.sigspec.tones_persymb)]
            c.fHz = int((c.f0_idx + bpt // 2) * self.df)
            c.last_payload_hop = np.max([c.syncs[0]['h0_idx'], c.syncs[1]['h0_idx']]) + hps * self.sigspec.payload_symb_idxs[-1]
            c.cyclestart_str = cyclestart_str            
            cands.append(c)
        return cands

            
