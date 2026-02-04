
import numpy as np
import time
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder
from PyFT8.osd import osd_decode_minimal

params = {
'MIN_LLR0_SD': 1,                # global minimum llr_sd
'MIN_SNR': -24,
'LDPC_CONTROL': (33, 10, 4),         # max ncheck0, 
'OSD_CONTROL': (25, [30,20]) # min llr_sd, max llr_sd, L(order)
}

class Candidate:
    def __init__(self):
        self.dedupe_key = ""
        self.demap_started, self.demap_completed, self.decode_completed = None, None, None
        self.cyclestart_str = ""
        self.dt = 0
        self.td = 0
        self.fHz = 0
        self.ncheck, self.ncheck0 = 99, 99
        self.llr0_sd = 0
        self.llr = []
        self.llr0 = []
        self.decode_path = ""
        self.msg = ''
        self.snr = -30
        self.ldpc = LdpcDecoder()

    def _flip_bits(self, llr, ncheck, width, nbits, keep_best = False):
        import itertools
        cands = np.argsort(np.abs(llr))
        idxs = cands[:nbits]
        
        best = {'llr':llr.copy(), 'nc':ncheck}
        for k in range(1, width + 1):
            for comb in itertools.combinations(range(len(idxs)), k):
                llr[idxs[list(comb)]] *= -1
                n = self.ldpc.calc_ncheck(llr)
                if n < best['nc']:
                    best = {'llr':llr.copy(), 'nc':n}
                    if n == 0:
                        return best['llr'], 0
                if n >= best['nc'] or not keep_best:
                    llr[idxs[list(comb)]] *= -1
        return best['llr'], best['nc']

    def _get_llr(self, pgrid_main, h0_idx, hps, freq_idxs, payload_symb_idxs, target_params = (3.3, 3.7)):
        hops = np.array([h0_idx + hps* s for s in payload_symb_idxs])
        praw = pgrid_main[np.ix_(hops, freq_idxs)]
        pgrid = np.clip(praw, np.max(praw)-120, None)
        snr = int(np.max(pgrid)) - 107
        if(snr >= params['MIN_SNR']):
            llra = np.max(pgrid[:, [4,5,6,7]], axis=1) - np.max(pgrid[:, [0,1,2,3]], axis=1)
            llrb = np.max(pgrid[:, [2,3,4,7]], axis=1) - np.max(pgrid[:, [0,1,5,6]], axis=1)
            llrc = np.max(pgrid[:, [1,2,6,7]], axis=1) - np.max(pgrid[:, [0,3,4,5]], axis=1)
            llr0 = np.column_stack((llra, llrb, llrc))
            llr0 = llr0.ravel() / 10
            llr0_sd = int(0.5+100*np.std(llr0))/100.0
            if (llr0_sd > params['MIN_LLR0_SD']):
                llr0 = target_params[0] * llr0 / llr0_sd
                llr0 = np.clip(llr0, -target_params[1], target_params[1])
                snr = int(np.clip(snr, -24, 24))
            return (llr0, llr0_sd, pgrid, snr)
        else:
            return ([],0,[],-30)
        
    def demap(self, spectrum):
        self.demap_started = time.time()
        h0, h1 = self.syncs[0]['h0_idx'], self.syncs[1]['h0_idx']
        if(h0 == h1): h1 = h0 +1
        demap0 = self._get_llr(spectrum.audio_in.pgrid_main, h0, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        demap1 = self._get_llr(spectrum.audio_in.pgrid_main, h1, spectrum.hops_persymb, self.freq_idxs, spectrum.sigspec.payload_symb_idxs)
        sync_idx =  0 if demap0[1] > demap1[1] else 1
        demap = [demap0, demap1][sync_idx]
        quality_too_low = (demap[1] == 0 )
        if(quality_too_low):
            self._record_state("I", final = True)
            self.demap_completed = time.time()
            return
        self.h0_idx = self.syncs[sync_idx]['h0_idx']
        self.sync_score = self.syncs[sync_idx]['score']
        self.dt = int(0.5+100*self.syncs[sync_idx]['dt'])/100.0
        self.p_dB = 10*demap[2]
        self.llr0, self.llr0_sd, self.pgrid, self.snr = demap
        self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
        self.llr = self.llr0.copy()
        self.ncheck = self.ncheck0
        self._record_state("I")
        self.demap_completed = time.time()

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ""
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def decode(self):
        if not self.decode_completed and params['LDPC_CONTROL'][0] > self.ncheck > 0:
            for it in range(params['LDPC_CONTROL'][1]):
                self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
                self._record_state("L")
                if(self.ncheck == 0):
                    break

        if(self.ncheck == 0):  
            codeword_bits = (self.llr > 0).astype(int).tolist()
            self.check_crc_and_get_message(codeword_bits)

        if(0 < self.ncheck < params['OSD_CONTROL'][0]):
            reliab_order = np.argsort(np.abs(self.llr))[::-1]
            codeword_bits = osd_decode_minimal(self.llr0, reliab_order, Ls = params['OSD_CONTROL'][1])
            self.check_crc_and_get_message(codeword_bits)
            if(self.msg):
                self.ncheck = 0
            self._record_state("O")

        self._record_state("M" if self.msg else "_", final = True)

    def check_crc_and_get_message(self, codeword_bits):
        if check_crc_codeword_list(codeword_bits):
            if(any(codeword_bits[:77])):
                self.msg = FT8_unpack(codeword_bits[:77])


