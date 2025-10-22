import numpy as np

from PyFT8.FT8_constants import kNCW, kNRW, kMN, kNM, kN, kK, kM

def fast_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return 0.5 * np.log((1 + x) / (1 - x))

def safe_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return np.arctanh(x)

def decode174_91(llr, maxiterations = 50, alpha = 1.0, nstall_max = 12, ncheck_max = 30):
    toc = np.zeros((7, kM), dtype=np.float32)       # message -> check messages
    tanhtoc = np.zeros((7, kM), dtype=np.float64)
    tov = np.zeros((kNCW, kN), dtype=np.float32)    # check -> message messages
    nclast, nstall = 0, 0                           # stall condition variables
    info = []                           # record the progression of ncheck
    zn = np.copy(llr)                   # working copy of llrs
    rng = np.max(llr) - np.min(llr)     # indication of scale of llrs
    mult = rng * 5000 / 200000          # empricical multiplier for tov, proportional to llr scale
    for it in range(maxiterations + 1):
        for i in range(kN):
            zn[i] += mult*sum(tov[:,i])

        cw = (zn > 0).astype(int)
        ncheck = 0                      # syndrome: sum variable nodes participating in this check.
        for chk in range(kM):
            vars_idx = kNM[chk, :kNRW[chk]]
            if( int(np.sum(cw[vars_idx]) % 2)):
                ncheck += 1

        info.append(ncheck)
        if ncheck == 0:
            message91 = cw.tolist()
            if(sum(message91)>0):
               # print(f"Success: {info}")
                return message91, it

        nstall = 0 if ncheck < nclast else nstall +1
        nclast = ncheck
        if(nstall > nstall_max or ncheck > ncheck_max):         # early exit condition
         #   print(f"Failure: {info}")
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
                    if chknum == 0 or chknum == (j + 1): # kMN = 0 means "skip this check" (true?)
                        continue
                    toc[i_local, j] -= tov[kk, ibj]

        # tanh of half negative (what's this?)
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

    # failed to decode
   # print(f"Failure: {info}")
    return [], it

