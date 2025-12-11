
import numpy as np
import PyFT8.timers as timers

eps = 1e-12

class Candidate:
    next_id = 0
    def __init__(self, spectrum):
        self.id = Candidate.next_id
        Candidate.next_id +=1
        self.sigspec = spectrum.sigspec
        self.size = spectrum.candidate_size
        self.cycle_start = 15*int(timers.tnow()/15)
        self.cyclestart_str = timers.cyclestart_str()
        self.sync_result = None
        self.sync_score = 0
        self.synced_grid_complex = None
        self.sync_returned = None
        self.demap_requested = False
        self.demap_returned = None
        self.ldpc_requested = False
        self.ldpc_result = None
        self.ldpc_returned = None
        self.message_decoded = None
        self.ncheck_initial = 5000
        
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
        self.slack_hops =  int(self.hops_persymb * (self.sigspec.symbols_persec * self.sigspec.cycle_seconds - self.sigspec.num_symbols))

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
            for t0_idx in range(c_zgrid.shape[0] - n_hops_costas):
                test = (t0_idx, float(np.dot(c_pgrid[t0_idx + spectrum.hop_idxs_Costas ,  :].ravel(), spectrum._csync.ravel())))
                if test[1] > best[1]:
                    best = test
            if(best[1] > sync_score_thresh):
                c = Candidate(spectrum)
                c.sync_score = best[1]
                c.origin = (best[0], f0_idx, spectrum.dt * best[0], spectrum.df * (f0_idx + 1))
                neighbour_lf = [n for n in candidates if (c.origin[1] - n.origin[1] <=2)]
                if(neighbour_lf):
                    if(neighbour_lf[0].sync_score >= c.sync_score):
                        continue
                    if(neighbour_lf[0].sync_score < c.sync_score):
                        candidates.remove(neighbour_lf[0])
                candidates.append(c)
                c.last_hop = t0_idx + spectrum.candidate_size[0]
                c.last_data_hop = t0_idx + spectrum.candidate_size[0] - n_hops_costas
                c.first_data_hop = t0_idx + n_hops_costas
                c.sync_returned = timers.tnow()
        return candidates

    def demap_symbols(self, p):
        tones1 = [np.where(self.sigspec.gray_map[:,b]==1)[0] for b in range(3)]
        tones0 = [np.where(self.sigspec.gray_map[:,b]==0)[0] for b in range(3)]
        llr = np.empty((p.shape[0], 3), dtype=np.float32)
        for b in range(3):
            t1 = tones1[b]
            t0 = tones0[b]
            ones  = np.max(p[:, t1], axis=1)
            zeros = np.max(p[:, t0], axis=1)
            llr[:, b] = np.log(ones+eps) - np.log(zeros+eps)
        return llr.reshape(-1)

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
        llr = self.demap_symbols(pwr_payload)

        llr = llr - np.mean(llr)
        llr_sd = np.std(llr)
        return llr, llr_sd, snr


