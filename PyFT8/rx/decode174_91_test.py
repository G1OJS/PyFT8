import numpy as np

from PyFT8.FT8_constants import kNCW, kNRW, kMN, kNM, kN, kK, kM

def decode174_91(llr):
    maxiterations = 100
    llr = np.asarray(llr, dtype=np.float32)
    toc = np.zeros((7, kM), dtype=np.float32)
    tov = np.zeros((kNCW, kN), dtype=np.float32)
    tov_tmp = np.zeros((kM, kN), dtype=np.float32)  # 7 = max(kNRW)

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
            # note that synd doesn't *need* to be an array unless it's used for debugging
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

        alpha = 0.9
        for j in range(kM):
            deg = kNRW[j]
            msgs = toc[:deg, j]

            # overall sign of product
            sign_all = np.sign(msgs).prod()
            absmsg = np.abs(msgs)

            # smallest and second-smallest magnitudes
            i_min1 = np.argmin(absmsg)
            min1 = absmsg[i_min1]
            tmp = absmsg.copy(); tmp[i_min1] = np.inf
            min2 = tmp.min()

            # send message to each variable connected to this check
            for i_local in range(deg):
                var = int(kNM[j, i_local])
                mag = min2 if i_local == i_min1 else min1
                sgn = sign_all * np.sign(msgs[i_local])
                tov_tmp[j, var] = alpha * sgn * mag

        # after the loop, make tov the same shape as before by summing over checks
        tov = np.zeros((kNCW, kN), dtype=np.float32)
        for var in range(kN):
            # collect all non-zero entries from tov_tmp[:, var]
            nonzero_msgs = tov_tmp[:, var][tov_tmp[:, var] != 0]
            count = min(len(nonzero_msgs), kNCW)
            tov[:count, var] = nonzero_msgs[:count]


    # failed to decode
    print(f"Failure: {info}")
    return []

