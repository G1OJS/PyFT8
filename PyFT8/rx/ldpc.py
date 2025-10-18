import numpy as np

def safe_atanh(x, eps=1e-12):
    # clip to avoid |x| >= 1 domain errors
    x = np.clip(x, -1 + eps, 1 - eps)
    return np.arctanh(x)

def decode174_91(llr):

    ncw = 3
    Mn = np.array([[15,44,72],[24,50,61],[32,57,77],[0,43,44],[1,6,60],[2,5,53],[3,34,47],[4,12,20],[7,55,78],[8,63,68],[9,18,65],[10,35,59],[11,36,57],[13,31,42],[14,62,79],[16,27,76],[17,73,82],[21,52,80],[22,29,33],[23,30,39],[25,40,75],[26,56,69],[28,48,64],[2,37,77],[4,38,81],[45,49,72],[50,51,73],[54,70,71],[43,66,71],[42,67,77],[0,31,58],[1,5,70],[3,15,53],[6,64,66],[7,29,41],[8,21,30],[9,17,75],[10,22,81],[11,27,60],[12,51,78],[13,49,50],[14,80,82],[16,28,59],[18,32,63],[19,25,72],[20,33,39],[23,26,76],[24,54,57],[34,52,65],[35,47,67],[36,45,74],[37,44,46],[38,56,68],[40,55,61],[19,48,52],[45,51,62],[44,69,74],[26,34,79],[0,14,29],[1,67,79],[2,35,50],[3,27,50],[4,30,55],[5,19,36],[6,39,81],[7,59,68],[8,9,48],[10,43,56],[11,38,58],[12,23,54],[13,20,64],[15,70,77],[16,29,75],[17,24,79],[18,60,82],[21,37,76],[22,40,49],[6,25,57],[28,31,80],[32,39,72],[17,33,47],[12,41,63],[4,25,42],[46,68,71],[53,54,69],[44,61,67],[9,62,66],[13,65,71],[21,59,73],[34,38,78],[0,45,63],[0,23,65],[1,4,69],[2,30,64],[3,48,57],[0,3,4],[5,59,66],[6,31,74],[7,47,81],[8,34,40],[9,38,61],[10,13,60],[11,70,73],[12,22,77],[10,34,54],[14,15,78],[6,8,15],[16,53,62],[17,49,56],[18,29,46],[19,63,79],[20,27,68],[21,24,42],[12,21,36],[1,46,50],[22,53,73],[25,33,71],[26,35,36],[20,35,62],[28,39,43],[18,25,56],[2,45,81],[13,14,57],[32,51,52],[29,42,51],[5,8,51],[26,32,64],[24,68,72],[37,54,82],[19,38,76],[17,28,55],[31,47,70],[41,50,58],[27,43,78],[33,59,61],[30,44,60],[45,67,76],[5,23,75],[7,9,77],[39,40,69],[16,49,52],[41,65,67],[3,21,71],[35,63,80],[12,28,46],[1,7,80],[55,66,72],[4,37,49],[11,37,63],[58,71,79],[2,25,78],[44,75,80],[0,64,73],[6,17,76],[10,55,58],[13,38,53],[15,36,65],[9,27,54],[14,59,69],[16,24,81],[19,29,30],[11,66,67],[22,74,79],[26,31,61],[23,68,74],[18,20,70],[33,52,60],[34,45,46],[32,58,75],[39,42,82],[40,41,62],[48,74,82],[19,43,47],[41,48,56]], dtype=int)
    Nm = np.array([[3,30,58,90,91,95,152],[4,31,59,92,114,145,0],[5,23,60,93,121,150,0],[6,32,61,94,95,142,0],[7,24,62,82,92,95,147],[5,31,63,96,125,137,0],[4,33,64,77,97,106,153],[8,34,65,98,138,145,0],[9,35,66,99,106,125,0],[10,36,66,86,100,138,157],[11,37,67,101,104,154,0],[12,38,68,102,148,161,0],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[14,41,58,105,122,158,0],[0,32,71,105,106,156,0],[15,42,72,107,140,159,0],[16,36,73,80,108,130,153],[10,43,74,109,120,165,0],[44,54,63,110,129,160,172],[7,45,70,111,118,165,0],[17,35,75,88,112,113,142],[18,37,76,103,115,162,0],[19,46,69,91,137,164,0],[1,47,73,112,127,159,0],[20,44,77,82,116,120,150],[21,46,57,117,126,163,0],[15,38,61,111,133,157,0],[22,42,78,119,130,144,0],[18,34,58,72,109,124,160],[19,35,62,93,135,160,0],[13,30,78,97,131,163,0],[2,43,79,123,126,168,0],[18,45,80,116,134,166,0],[6,48,57,89,99,104,167],[11,49,60,117,118,143,0],[12,50,63,113,117,156,0],[23,51,75,128,147,148,0],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[20,53,76,99,139,170,0],[34,81,132,141,170,173,0],[13,29,82,112,124,169,0],[3,28,67,119,133,172,0],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[51,83,109,114,144,167,0],[6,49,80,98,131,172,0],[22,54,66,94,171,173,0],[25,40,76,108,140,147,0],[1,26,40,60,61,114,132],[26,39,55,123,124,125,0],[17,48,54,123,140,166,0],[5,32,84,107,115,155,0],[27,47,69,84,104,128,157],[8,53,62,130,146,154,0],[21,52,67,108,120,173,0],[2,12,47,77,94,122,0],[30,68,132,149,154,168,0],[11,42,65,88,96,134,158],[4,38,74,101,135,166,0],[1,53,85,100,134,163,0],[14,55,86,107,118,170,0],[9,43,81,90,110,143,148],[22,33,70,93,126,152,0],[10,48,87,91,141,156,0],[28,33,86,96,146,161,0],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[21,56,84,92,139,158,0],[27,31,71,102,131,165,0],[27,28,83,87,116,142,149],[0,25,44,79,127,146,0],[16,26,88,102,115,152,0],[50,56,97,162,164,171,0],[20,36,72,137,151,168,0],[15,46,75,129,136,153,0],[2,23,29,71,103,138,0],[8,39,89,105,133,150,0],[14,57,59,73,110,149,162],[17,41,78,143,145,151,0],[24,37,64,98,121,159,0],[16,41,74,128,169,171,0]], dtype=int)
    nrw = np.array([7, 6, 6, 6, 7, 6, 7, 6, 6, 7, 6, 6, 7, 7, 6, 6, 6, 7, 6, 7, 6, 7, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 7, 6, 6, 6, 6, 7, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 7, 7, 6, 6, 7, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6], dtype=int)
    
    N = 174
    K = 91
    M = N - K

    maxiterations = 30

    llr = np.asarray(llr, dtype=float)
    toc = np.zeros((7, M))          # message -> check messages
    tanhtoc = np.zeros((7, M))
    tov = np.zeros((ncw, N))        # check->message messages

    for it in range(maxiterations + 1):
        zn = np.copy(llr)
        zn += tov.sum(axis=0)
        
        cw = (zn > 0).astype(int)
        # syndrome
        ncheck = 0
        synd = np.zeros(M, dtype=int)
        for chk in range(M):
            # sum variable nodes participating in this check
            # Nm stores 1-based variable indices in each row; use first nrw[chk] entries
            vars_idx = Nm[chk, :nrw[chk]]
            synd[chk] = int(np.sum(cw[vars_idx]) % 2)
            if synd[chk] != 0:
                ncheck += 1

        # success
        if ncheck == 0:
            message91 = cw[:K].tolist()

            # compute dmin and ntype if present (preserve old behavior)
            try:
                hdec = (llr > 0).astype(int)
                nxor = np.bitwise_xor(hdec, cw)
                dmin[0] = np.sum(nxor * np.abs(llr))
                ntype[0] = 1
            except NameError:
                # dmin/ntype not defined: ignore
                pass
            return message91

        # compute toc = messages from variable node -> check node
        # For each check node j, for each connected variable i
        for j in range(M):
            for i_local in range(nrw[j]):         # 0 .. nrw[j]-1
                ibj = int(Nm[j, i_local])         # variable node index (0-based)
                toc[i_local, j] = zn[ibj]
                # subtract messages from checks (tov) that correspond to other checks connected to variable ibj
                # Mn[ibj, :] lists checks (1-based) that connect to variable ibj
                for kk in range(ncw):
                    chknum = Mn[ibj, kk]
                    if chknum == 0:
                        # if Mn uses 0 as sentinel for "no more checks", skip
                        continue
                    if chknum == (j + 1):
                        # skip the current check (do not subtract its message)
                        continue
                    tov_idx = kk
                    tov_val = tov[tov_idx, ibj]
                    toc[i_local, j] -= tov_val

        # tanh of half negative (matching original)
        for j in range(M):
            tanhtoc[:nrw[j], j] = np.tanh(-toc[:nrw[j], j] / 2.0)

        # compute tov (check->variable messages)
        # for each variable node j, it connects to ncw checks (Mn[j, :])
        for var in range(N):
            # iterate check-positions kk for this variable
            for kk in range(ncw):
                chknum = Mn[var, kk]
                if chknum == 0:
                    # sentinel / unused
                    tov[kk, var] = 0.0
                    continue
                ichk = int(chknum)   # check index 0-based
                # build mask over the neighbours of check ichk excluding current variable 'var'
                neigh_count = nrw[ichk]
                neigh_vars = Nm[ichk, :neigh_count]  
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
                alpha = 0.3   # 0 < alpha <= 1 ; try 0.3..0.9. lower = more damping
                new_val = 2.0 * safe_atanh(-Tmn)
                tov[kk, var] = alpha * new_val + (1 - alpha) * tov[kk, var]

    # failed to decode
    return []

