
import numpy as np
import time
from PyFT8.FT8_unpack import unpack
from PyFT8.FT8_crc import check_crc
from PyFT8.ldpc import LdpcDecoder

params = {
'MIN_LLR_SD': 0.5,           # global minimum llr_sd
'LDPC_CONTROL': (45, 12),         # max ncheck0, max iterations         
}

class Candidate:
    def __init__(self):

        self.demap_started, self.decode_completed = False, False
        self.ncheck0, self.ncheck = 99, 99
        self.llr_sd = 0
        self.decode_path = ''
        self.decode_dict = False
        self.processing_time = 0
        self.cyclestart_str = ''
        self.msg = ''
        # decode_dict is set in spectrum search
        self.ldpc = LdpcDecoder()

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ""
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def demap(self, spectrum, target_params = (3.3, 3.7)):
        self.demap_started = time.time()
        hops = self.sync['h0_idx'] + spectrum.base_payload_hops
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
        self.decode_dict.update({'llr_sd':self.llr_sd})
          
    def decode(self):
        decode_started = time.time()
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
            bits91_int = 0
            for bit in (self.llr[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            if(bits77_int):
                self.msg = unpack(bits77_int)

        self._record_state("M" if self.msg else "_", final = True)

        self.decode_dict.update( {
                            'msg_tuple':self.msg,
                            'msg':' '.join(self.msg),
                            'llr_sd':self.llr_sd,
                            'decode_path':self.decode_path,
                            'ncheck0': self.ncheck0,
                            'snr': np.clip(int(np.max(self.dB) - np.min(self.dB) - 58), -24, 24),
                            'td': f"{time.time() %60:4.1f}"
                           })
        

