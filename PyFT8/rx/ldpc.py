import numpy as np

from PyFT8.FT8_constants import kNCW, kNRW, kMN, kNM, kN, kK, kM

def safe_atanh(x, eps=1e-12):
    # clip to avoid |x| >= 1 domain errors
    x = np.clip(x, -1 + eps, 1 - eps)
    return np.arctanh(x)

def decode174_91(llr):
    maxiterations = 10
    llr = np.asarray(llr, dtype=float)
    toc = np.zeros((7, kM))          # message -> check messages
    tanhtoc = np.zeros((7, kM))
    tov = np.zeros((kNCW, kN))        # check->message messages

    info = []
    for it in range(maxiterations + 1):
        zn = np.copy(llr)
        zn += tov.sum(axis=0)
        
        cw = (zn > 0).astype(int)
        # syndrome
        ncheck = 0
        synd = np.zeros(kM, dtype=int)
        for chk in range(kM):
            # sum variable nodes participating in this check
            # kNM stores 1-based variable indices in each row; use first kNRW[chk] entries
            vars_idx = kNM[chk, :kNRW[chk]]
            synd[chk] = int(np.sum(cw[vars_idx]) % 2)
            if synd[chk] != 0:
                ncheck += 1

        info.append(ncheck)
        # success
        if ncheck == 0:
            message91 = cw.tolist()
            if(sum(message91)>0):
                print(f"Success: {info}")
                return message91

        # compute toc = messages from variable node -> check node
        # For each check node j, for each connected variable i
        for j in range(kM):
            for i_local in range(kNRW[j]):         # 0 .. kNRW[j]-1
                ibj = int(kNM[j, i_local])         # variable node index (0-based)
                toc[i_local, j] = zn[ibj]
                # subtract messages from checks (tov) that correspond to other checks connected to variable ibj
                # kMN[ibj, :] lists checks (1-based) that connect to variable ibj
                for kk in range(kNCW):
                    chknum = kMN[ibj, kk]
                    if chknum == 0:
                        # if kMN uses 0 as sentinel for "no more checks", skip
                        continue
                    if chknum == (j + 1):
                        # skip the current check (do not subtract its message)
                        continue
                    tov_idx = kk
                    tov_val = tov[tov_idx, ibj]
                    toc[i_local, j] -= tov_val

        # tanh of half negative (matching original)
        for j in range(kM):
            tanhtoc[:kNRW[j], j] = np.tanh(-toc[:kNRW[j], j] / 2.0)

        # compute tov (check->variable messages)
        # for each variable node j, it connects to kNCW checks (kMN[j, :])
        for var in range(kN):
            # iterate check-positions kk for this variable
            for kk in range(kNCW):
                chknum = kMN[var, kk]
                if chknum == 0:
                    # sentinel / unused
                    tov[kk, var] = 0.0
                    continue
                ichk = int(chknum)   # check index 0-based
                # build mask over the neighbours of check ichk excluding current variable 'var'
                neigh_count = kNRW[ichk]
                neigh_vars = kNM[ichk, :neigh_count]  
                # mask which entries are not equal to this var index
                mask = (neigh_vars != var)
                if mask.sum() == 0:
                    # no other neighbours => product is 1? set small value
                    Tmn = 0.0
                else:
                    # product of tanh values for other edges
                    tvals = tanhtoc[:neigh_count, ichk][mask]
                    # product; make sure to handle empty product
                    Tmn = np.prod(tvals) if tvals.size > 0 else 0.0

                # inverse tanh (clipped)
                y = safe_atanh(-Tmn)
                alpha = 1   # 0 < alpha <= 1 ; try 0.3..0.9. lower = more damping
                new_val = 2.0 * safe_atanh(-Tmn)
                tov[kk, var] = alpha * new_val + (1 - alpha) * tov[kk, var]

    # failed to decode
    print(f"Failure: {info}")
    return []

