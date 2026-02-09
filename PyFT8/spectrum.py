
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
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * self.hops_persymb)
        self.audio_in = AudioIn(self.sigspec.cycle_seconds, self.hops_percycle, self.sigspec.symbols_persec, hops_persymb, fbins_pertone, max_freq)
        self.nFreqs = self.audio_in.nFreqs
        self.dt = 1.0 / (self.sigspec.symbols_persec * self.hops_persymb) 
        self.df = max_freq / (self.nFreqs -1)
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * self.hops_persymb
        self.nhops_costas = self.sigspec.costas_len * self.hops_persymb
        self.h_search1 = int(4.6/self.dt)
        self.h_search2 = int(10.4/self.dt)
        self.hop_start_lattitude = int(3.48/self.dt)
        self.occupancy = np.zeros(self.nFreqs)
        self.csync_flat = self.make_csync(sigspec)

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -self.fbins_pertone / (self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def get_sync(self, f0_idx, pnorm, sync_idx):
        best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
        h0_min = 0 if sync_idx == 0 else -7*self.hops_persymb
        for h0_idx in range(h0_min, self.hop_start_lattitude):
            sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas + sync_idx * 36 * self.hops_persymb ,  :].ravel(), self.csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * self.dt - 0.7}
            if test_sync['score'] > best_sync['score']:
                best_sync = test_sync
        return best_sync
    
    def search(self, f0_idxs, cyclestart_str, sync_idx):
        hps, bpt = self.hops_persymb, self.fbins_pertone
        cands = []
        dB_main = self.audio_in.dB_main
        for f0_idx in f0_idxs:
            dB = dB_main[:, f0_idx:f0_idx + self.fbins_per_signal]
            c = Candidate()
            c.f0_idx = f0_idx
            c.sync = self.get_sync(f0_idx, dB, sync_idx)
            c.freq_idxs = [c.f0_idx + bpt // 2 + bpt * t for t in range(self.sigspec.tones_persymb)]
            c.fHz = int((c.f0_idx + bpt // 2) * self.df)
            c.last_payload_hop = c.sync['h0_idx'] + hps * 72
            c.cyclestart_str = cyclestart_str
            c.sync_idx = sync_idx
            c.decode_dict = {'cs':c.cyclestart_str, 'f':c.fHz, 'msg_tuple':(''), 'msg':'',
                             'llr_sd':0, 'decode_path':'',
                             'h0_idx': c.sync['h0_idx'],
                             'f0_idx': c.f0_idx,
                             'ncheck': 99,
                             'ncheck0': 99,
                             'sync_idx': 0, 
                             'sync_score': c.sync['score'],
                             'snr': -30,
                             'dt': int(0.5+100*c.sync['dt'])/100.0, 
                             'td': 0}

            
            cands.append(c)
        return cands


