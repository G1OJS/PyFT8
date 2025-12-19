
import numpy as np
eps = 1e-12

class Candidate:
    next_id = 0
    def __init__(self, spectrum):
        self.id = Candidate.next_id
        Candidate.next_id +=1
        self.sigspec = spectrum.sigspec
        self.size = spectrum.candidate_size
        self.sync_score = 0
        self.synced_grid_complex = False
        self.demap_requested = False
        self.demap_returned = False
        self.ldpc_requested = False
        self.ldpc_returned = False
        self.ncheck_initial = 5000
        self.cyclestart_str = None
        
class FT8Demodulator:
    def __init__(self, sigspec):
        self.sigspec = sigspec
        self.sample_rate=12000
        self.fbins_pertone=3
        self.hops_persymb=3
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hops_per_costas_block = self.hops_persymb * self.sigspec.costas_len
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )
        self.hops_persec = self.sample_rate / self.samples_perhop 
        self.slack_hops =  int(self.hops_persymb * (self.sigspec.symbols_persec * self.sigspec.cycle_seconds - (self.sigspec.num_symbols - self.sigspec.costas_len) ) )

    def find_syncs(self, spectrum, sync_score_thresh):
        candidates = []
        n_hops_costas = np.max(spectrum.hop_idxs_Costas)
        f0_idxs = range(spectrum.nFreqs - spectrum.candidate_size[1])
        zgrid = spectrum.fine_grid_complex
        for f0_idx in f0_idxs:
            c_zgrid = zgrid[: n_hops_costas + self.slack_hops, f0_idx:f0_idx + self.fbins_per_signal]
            c_pgrid = np.abs(c_zgrid)**2
            max_pwr = np.max(c_pgrid)
            spectrum.occupancy[f0_idx:f0_idx + self.fbins_per_signal] += max_pwr
            c_pgrid = c_pgrid / (max_pwr + eps)
            best = (0, -1e30)
            for t0_idx in range(self.slack_hops):
                test = (t0_idx, float(np.dot(c_pgrid[t0_idx + spectrum.hop_idxs_Costas ,  :].ravel(), spectrum._csync.ravel())))
                if test[1] > best[1]:
                    best = test
            if(best[1] > sync_score_thresh):
                c = Candidate(spectrum)
                c.sync_score = best[1]
                c.origin = (best[0], f0_idx, spectrum.dt * best[0], spectrum.df * (f0_idx + 1))
                candidates.append(c)
                c.last_hop = best[0] + spectrum.candidate_size[0]
                c.last_data_hop = best[0] + spectrum.candidate_size[0] - n_hops_costas
                c.first_data_hop = best[0] + n_hops_costas
        return candidates

    def _demap_symbols(self, p):
        llr0 = np.log(np.max(p[:,[4,5,6,7]], axis=1)) - np.log(np.max(p[:,[0,1,2,3]], axis=1))
        llr1 = np.log(np.max(p[:,[2,3,4,7]], axis=1)) - np.log(np.max(p[:,[0,1,5,6]], axis=1))
        llr2 = np.log(np.max(p[:,[1,2,6,7]], axis=1)) - np.log(np.max(p[:,[0,3,4,5]], axis=1))
        return np.column_stack((llr0, llr1, llr2)).ravel()

    def demap_candidate(self, c):
        origin = c.origin
        synced_grid_complex = c.synced_grid_complex.reshape(self.sigspec.num_symbols, self.hops_persymb,
                                                          self.sigspec.tones_persymb, self.fbins_pertone)
        synced_grid_complex = synced_grid_complex[:,0,:,:] # first hop of self.hops_persymb = the one we synced to
        synced_grid_pwr = np.abs(synced_grid_complex)**2
        synced_pwr = np.max(synced_grid_pwr)
        snr = 10*np.log10(synced_pwr)-107
        snr = int(np.clip(snr, -24,24).item())
        synced_grid_pwr_central = synced_grid_pwr[:,:,1]/synced_pwr
        pwr_payload = synced_grid_pwr_central[self.sigspec.payload_symb_idxs]
        llr = self._demap_symbols(pwr_payload)
        return llr, snr


