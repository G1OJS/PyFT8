
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
        self.h_search2 = int(11/self.dt)
        self.search_hops_range = range(int((-1.7 + 0.7) / self.dt), int((3.2 + 0.7) / self.dt))
        self.occupancy = np.zeros(self.nFreqs)
        self.csync_flat = self.make_csync(sigspec)
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
        data_symb_idxs = list(range(7, 36)) + list(range(43, 45))
        self.base_payload_hops = np.array([hops_persymb * s for s in payload_symb_idxs])
        self.base_data_hops = np.array([hops_persymb * s for s in data_symb_idxs])

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -self.fbins_pertone / (self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone * self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def get_sync(self, f0_idx, pnorm, sync_idx):
        best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
        for h0_idx in self.search_hops_range:
            sync_score = float(np.dot(pnorm[h0_idx + self.hop_idxs_Costas + sync_idx * 36 * self.hops_persymb ,  :].ravel(), self.csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * self.dt - 0.7}
            if test_sync['score'] > best_sync['score']:
                best_sync = test_sync
        return best_sync
    
    def search(self, f0_idxs, cyclestart_str):
        cands = []
        dB_main = self.audio_in.dB_main
        hps, bpt = self.hops_persymb, self.fbins_pertone
        for f0_idx in f0_idxs:
            dB = dB_main[:, f0_idx:f0_idx + self.fbins_per_signal]
            dB = dB - np.max(dB)
            c = Candidate()
            c.f0_idx = f0_idx
            sync_idx = 1
            c.sync = self.get_sync(f0_idx, dB, sync_idx)
            c.freq_idxs = [c.f0_idx + bpt // 2 + bpt * t for t in range(self.sigspec.tones_persymb)]
            c.last_payload_hop = c.sync['h0_idx'] + hps * 72
            c.cyclestart_str = cyclestart_str
            c.decode_dict = {'decoder': 'PyFT8',
                             'cs':c.cyclestart_str,
                             'f':int((c.f0_idx + bpt // 2) * self.df),
                             'f0_idx': c.f0_idx,
                             'sync_idx': sync_idx, 
                             'sync': c.sync,
                             'dt': int(0.5+100*c.sync['dt'])/100.0, 
                             'ncheck0': 99,
                             'snr': -30,
                             'llr_sd':0,
                             'decode_path':'',
                             'msg_tuple':(''), 'msg':'',
                             'td': 0}
            cands.append(c)
        return cands


