
import numpy as np
import time
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder
from PyFT8.osd import osd_decode_minimal

params = {
'MIN_SNR': -20,                # global min snr
'MIN_LLR0_SD': 0.65,           # global minimum llr_sd
'LDPC_CONTROL': (45, 12),      # max ncheck0, max iterations
'OSD_CONTROL': (0.8, [40,20])  # max llr0_sd, L(order)
}

class Candidate:
    def __init__(self, testing = False):

        self.demap_started, self.demap_completed, self.decode_completed = None, None, None
        self.dt, self.td, self.fHz = 0, 0, 0
        self.decode_path = ''
        self.cyclestart_str = ''
        self.msg = ''
        self.ldpc = LdpcDecoder()

    def _get_llr(self, spectrum, h0_idx, target_params = (3.3, 3.7)):
        hops = np.array([h0_idx + spectrum.hops_persymb * s for s in spectrum.sigspec.payload_symb_idxs])
        p_dB = spectrum.audio_in.pgrid_main[np.ix_(hops, self.freq_idxs)]
        p_max = np.max(p_dB)
        snr = int( p_max - np.min(p_dB) - 58)
        p = p_dB - p_max
        p = np.clip(p, -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr0 = np.column_stack((llra, llrb, llrc))
        llr0 = llr0.ravel() / 10
        llr0_sd = int(0.5+100*np.std(llr0))/100.0
        if (llr0_sd > params['MIN_LLR0_SD'] and snr >= params['MIN_SNR']):
            llr0 = target_params[0] * llr0 / llr0_sd
            llr0 = np.clip(llr0, -target_params[1], target_params[1])
            snr = int(np.clip(snr, -24, 24))
            return llr0, llr0_sd, p_dB, snr
        return [], 0, p_dB, -30
        
    def demap(self, spectrum):
        self.demap_started = time.time()
        h0, h1 = self.syncs[0]['h0_idx'], self.syncs[1]['h0_idx']
        if(h0 == h1): h1 = h0 +1
        demap0, demap1 = self._get_llr(spectrum, h0), self._get_llr(spectrum, h1)
        self.sync_idx =  0 if demap0[1] > demap1[1] else 1
        self.llr0, self.llr0_sd, self.p_dB, self.snr = [demap0, demap1][self.sync_idx]
        self.demap_completed = time.time()

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ""
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def decode(self):
        
        quality_too_low = (len(self.llr0)==0)
        if(quality_too_low):
            self.ncheck0, self.ncheck = 99, 99
            self._record_state("I", final = True)
            return
        self.ncheck0 = self.ldpc.calc_ncheck(self.llr0)
        self.ncheck = self.ncheck0
        codeword_bits = []
        self._record_state("I")

        if self.ncheck > 0:
            self.llr = self.llr0.copy()
            if self.ncheck <= params['LDPC_CONTROL'][0]:
                for it in range(params['LDPC_CONTROL'][1]):
                    self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
                    self._record_state("L")
                    if(self.ncheck == 0):
                        codeword_bits = (self.llr > 0).astype(int).tolist()
                        break

        if self.ncheck > 0:
            if(self.llr0_sd < params['OSD_CONTROL'][0]):
                reliab_order = np.argsort(np.abs(self.llr))[::-1]
                codeword_bits = osd_decode_minimal(self.llr0, reliab_order, Ls = params['OSD_CONTROL'][1])
                self._record_state("O")

        if(any(codeword_bits[:77])):
            if check_crc_codeword_list(codeword_bits):
                self.msg = FT8_unpack(codeword_bits[:77])
                self.h0_idx = self.syncs[self.sync_idx]['h0_idx']
                self.sync_score = self.syncs[self.sync_idx]['score']
                self.dt = int(0.5+100*self.syncs[self.sync_idx]['dt'])/100.0  

        self._record_state("M" if self.msg else "_", final = True)
