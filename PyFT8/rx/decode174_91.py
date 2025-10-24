# uses zero-based kNM and kMN arrays but clipped to zero, so the zeros
# interpreted as sentinels in the fortran code are here interpreted as
# pointers to the first element of the arrays - which is wrong, but this
# decodes more signals and faster ....

import numpy as np

from PyFT8.FT8_constants import kNCW, kNRW, kMN, kNM, kN, kK, kM
from PyFT8.FT8_crc import check_crc

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

def safe_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return 0.5 * np.log((1 + x) / (1 - x))
  #  return np.arctanh(x)

def count_syndrome_checks(zn):
    ncheck = 0
    cw = (zn > 0).astype(int)
    for i in range(kM):
        synd = sum(cw[kNM[i, 0:kNRW[i]]])
        if ((synd %2) != 0): ncheck += 1
    if ncheck == 0:
        decoded_bits174_LE_list = cw.tolist() 
        decoded_bits91_int = bitsLE_to_int(decoded_bits174_LE_list[0:91])
        if(not check_crc(decoded_bits91_int)):
            return -1, cw, []
        return 0, cw, decoded_bits174_LE_list
    return ncheck, cw, []

def decode174_91(llr, maxiterations = 50, alpha = 0.05, gamma = 0.03, nstall_max = 12, ncheck_max = 30):
    toc = np.zeros((7, kM), dtype=np.float32)       # message -> check messages
    tanhtoc = np.zeros((7, kM), dtype=np.float64)
    tov = np.zeros((kNCW, kN), dtype=np.float32)    # check -> message messages
    nclast, nstall = 0, 0                           # stall condition variables
    zn = np.copy(llr)                   # working copy of llrs
    rng = np.max(llr) - np.min(llr)     # indication of scale of llrs
    mult = rng * gamma          # empricical multiplier for tov, proportional to llr scale

    ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
    if(ncheck ==0): return decoded_bits174_LE_list, it

    for it in range(maxiterations + 1):
        for i in range(kN):
            zn[i] += mult*sum(tov[:,i])
            
        ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
        if(ncheck <=0): return decoded_bits174_LE_list, it
        
        nstall = 0 if ncheck < nclast else nstall +1
        nclast = ncheck
        if(nstall > nstall_max or ncheck > ncheck_max):         # early exit condition
            return [], it
        
        # compute toc = messages from variable node -> check node
        # For each check node j, for each connected variable i subtract messages from checks (tov)
        # that correspond to other checks connected to variable ibj (connections specified by kMN[ibj, :])
        for j in range(kM):
            for i_local in range(kNRW[j]):    
                ibj = int(kNM[j, i_local])   
                toc[i_local, j] = zn[ibj]
                for kk in range(kNCW):
                    chknum = kMN[ibj, kk]
                    if chknum == j:
                        continue
                    toc[i_local, j] -= tov[kk, ibj]

        for j in range(kM):
            tanhtoc[:kNRW[j], j] = np.tanh(-toc[:kNRW[j], j] / 2.0)

        # compute tov (check -> variable messages)
        # for each variable node j, it connects to kNCW checks (kMN[j, :])
        for variable_node in range(kN):
            for kk in range(kNCW):
                chknum = kMN[variable_node, kk]
                if chknum == 0:
                    tov[kk, variable_node] = 0.0
                    continue
                ichk = int(chknum)
                # build mask over the neighbours of check ichk excluding current variable 'var'
                neigh_count = kNRW[ichk]
                neigh_vars = kNM[ichk, :neigh_count]  
                mask = (neigh_vars != variable_node)
                if mask.sum() == 0:
                    Tmn = 0.0
                else:
                    tvals = tanhtoc[:neigh_count, ichk][mask]
                    Tmn = np.prod(tvals) if tvals.size > 0 else 0.0
                y = safe_atanh(-Tmn)
                new_val = 2.0 * safe_atanh(-Tmn)
                tov[kk, variable_node] = alpha * new_val + (1 - alpha) * tov[kk, variable_node]
    return [], it

