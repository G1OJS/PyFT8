
import numpy as np
import time
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.ldpc import LdpcDecoder

params = {
'MIN_LLR_SD': 0.65,           # global minimum llr_sd
'LDPC_CONTROL': (45, 12),         # max ncheck0, max iterations         
}

class Candidate:
    def __init__(self):

        self.demap_started, self.decode_completed = False, False
        self.ncheck, self.ncheck0 = 99, 99
        self.llr = []
        self.llr_sd = 0
        self.sync = []
        self.sync_idx = 0
        self.msg = ''
        self.ldpc = LdpcDecoder()
        self.decode_dict = {'decoder': 'PyFT8', 'cs':'000000_000000', 'f':0, 'msg_tuple':('','',''), 'msg':'',
                           'decode_path': '',
                           'ncheck0': 99,
                           'snr': -30, 'dt': 0, 'td':0}

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ""
        decode_path = self.decode_dict['decode_path']
        decode_path = self.decode_dict['decode_path'] + f"{actor_code}{self.ncheck:02d}{finalcode}"
        self.decode_dict.update({'decode_path':decode_path})
        if(final):
            self.decode_completed = True

    def demap(self, spectrum, target_params = (3.3, 3.7)):
        self.demap_started = True
        hops = np.array([self.sync['h0_idx'] + spectrum.hops_persymb * s for s in spectrum.sigspec.payload_symb_idxs])
        self.dB = spectrum.audio_in.dB_main[np.ix_(hops, self.freq_idxs)]
        p = np.clip(self.dB - np.max(self.dB), -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc))
        llr = llr.ravel() / 10
        self.llr_sd = int(0.5+100*np.std(llr))/100.0
        llr = target_params[0] * llr / (1e-12 + self.llr_sd)
        self.llr = np.clip(llr, -target_params[1], target_params[1])
          
    def decode(self):
        if(self.llr_sd < params['MIN_LLR_SD']):
            self._record_state("I", final = True)
            return
        self.ncheck = self.ldpc.calc_ncheck(self.llr)
        self.ncheck0 = self.ncheck
        self._record_state("I")

        if self.ncheck > 0:
            if self.ncheck <= params['LDPC_CONTROL'][0]:
                for it in range(params['LDPC_CONTROL'][1]):
                    self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
                    self._record_state("L")
                    if(self.ncheck == 0):
                        break                    
        if(self.ncheck == 0):
            codeword_bits = (self.llr > 0).astype(int).tolist()
            if(any(codeword_bits[:77])):
                if check_crc_codeword_list(codeword_bits):
                    self.msg = FT8_unpack(codeword_bits[:77])
                    self._record_state("M", final = True)
                    self.decode_dict.update({'msg_tuple':self.msg 'msg': ' '.join(self.msg)})

        self.decode_dict.update({ 'llr_sd':self.llr_sd, 'snr': np.clip(int(np.max(self.dB) - np.min(self.dB) - 58), -24, 24),
                                  'ncheck0': self.ncheck0,
                                  'td': f"{time.time() %60:4.1f}"})


