
import math
import numpy as np
from PyFT8.rx.decode174_91_v5_5 import LDPC174_91
import PyFT8.FT8_crc as crc
from PyFT8.comms_hub import config, send_to_ui_ws
import threading
import PyFT8.timers as timers

eps = 1e-12


    
class Candidate:
    next_id = 0
    def __init__(self, spectrum):
        self.id = Candidate.next_id
        Candidate.next_id +=1
        self.sigspec = spectrum.sigspec
        self.size = spectrum.candidate_size
        self.cyclestart_str = timers.cyclestart_str()
        self.sync_score = None
        self.sync_result = None
        self.synced_grid_complex = None
        self.demap_requested = False
        self.demap_result = None
        self.ldpc_requested = False
        self.ldpc_result = None
        self.ncheck_initial = 5000
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
        self.hops_persymb=3
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.hops_per_costas_block = self.hops_persymb * self.sigspec.costas_len
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )
        self.hops_persec = self.sample_rate / self.samples_perhop 
        self.slack_hops =  int(self.hops_persymb * (self.sigspec.symbols_persec * self.sigspec.cycle_seconds - self.sigspec.num_symbols))
        self.ldpc = LDPC174_91(max_iters, max_stall, max_ncheck)

    def find_syncs(self, spectrum, cyclestart_pointer, sync_score_thresh):
        candidates = []
        n_hops_costas = np.max(spectrum.hop_idxs_Costas)
        f0_idxs = range(spectrum.nFreqs - spectrum.candidate_size[1])
        zgrid = spectrum.fine_grid_complex
        for f0_idx in f0_idxs:
            c_zgrid = zgrid[cyclestart_pointer: cyclestart_pointer + n_hops_costas + self.slack_hops, f0_idx:f0_idx + self.fbins_per_signal]
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
                t0_idx = best[0] + cyclestart_pointer
                c.sync_result = {'sync_score': best[1], 
                                'origin': (t0_idx, f0_idx, spectrum.dt * t0_idx, spectrum.df * (f0_idx + 1)),
                                'last_hop': t0_idx + spectrum.candidate_size[0],
                                'last_data_hop': t0_idx + spectrum.candidate_size[0] - n_hops_costas,
                                'first_data_hop': t0_idx + n_hops_costas}
                neighbour_lf = [n for n in candidates if (c.sync_result['origin'][1] - n.sync_result['origin'][1] <=2)]
                if(neighbour_lf):
                    if(neighbour_lf[0].sync_result['sync_score'] >= c.sync_result['sync_score']): continue
                    if(neighbour_lf[0].sync_result['sync_score'] < c.sync_result['sync_score']): candidates.remove(neighbour_lf[0])
                c.timings.update({'sync':timers.tnow()})
                candidates.append(c)
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
            llr[:, b] = np.log(ones) - np.log(zeros)
        return llr.reshape(-1)

    def demap_candidate(self, c):
        origin = c.sync_result['origin']
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
        c.demap_result = {'llr_sd':llr_sd, 'llr':llr, 'snr':snr}

    def decode_candidate(self, candidate, onDecode):
        c = candidate
        llr = 3 * c.demap_result['llr'] / (c.demap_result['llr_sd']+.001)
        c.ldpc_result = self.ldpc.decode(llr)
        if(c.ldpc_result['payload_bits']):
            c.decode_result = FT8_unpack(c)
        onDecode(c)

#===========================================
# Experimental for pass 2
#===========================================

    def subtract(self, spectrum, c):
        import PyFT8.tx.FT8_encoder as FT8_encoder
        c1, c2, grid_rpt = c.message.split()
        symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
        if(symbols):
            origin = c.sync_result['origin']
            for i, s in enumerate(symbols):
                t0_cand, f0 = i*self.hops_persymb, self.fbins_pertone * s
                z_ref=c.synced_grid_complex[t0_cand, f0+1]
                t0 = t0_cand + origin[0]
                spectrum.fine_grid_complex[t0:t0+self.hops_persymb, f0-1:f0+1] -= z_ref
    
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
    decode_result = {'cyclestart_str':c.cyclestart_str , 'freq':freq_str,
                     'call_a':call_a, 'call_b':call_b, 'grid_rpt':grid_rpt,
                     't0_idx':origin[0], 'dt':time_str, 'snr':snr,
                     'n_its':c.ldpc_result['n_its'], 'ncheck_initial':c.ldpc_result['ncheck_initial']}
    return decode_result

