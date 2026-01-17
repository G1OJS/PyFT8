import numpy as np
import itertools
from PyFT8.ldpc import LdpcDecoder

ldpc = LdpcDecoder()

def flip_bits(llr, ncheck, width, nbits, keep_best = False):
    cands = np.argsort(np.abs(llr))
    idxs = cands[:nbits]
    
    best = {'llr':llr.copy(), 'nc':ncheck}
    for k in range(1, width + 1):
        for comb in itertools.combinations(range(len(idxs)), k):
            llr[idxs[list(comb)]] *= -1
            n = ldpc.calc_ncheck(llr)
            if n < best['nc']:
                best = {'llr':llr.copy(), 'nc':n}
                if n == 0:
                    return best['llr'], 0
            if n >= best['nc'] or not keep_best:
                llr[idxs[list(comb)]] *= -1
    return best['llr'], best['nc']
