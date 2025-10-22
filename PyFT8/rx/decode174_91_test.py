import numpy as np

from PyFT8.FT8_constants import kNCW, kNRW, kMN, kNM, kN, kK, kM

def safe_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return np.arctanh(x)

def _normalize_maps_to_zero_based_with_neg1_padding(kMN_in, kNM_in, kNRW_in):
    """
    Ensure:
      - kMN (N×3): variable -> check, values in [0..M-1], padding = -1
      - kNM (M×7): check   -> variable, values in [0..N-1], padding = -1
      - kNRW (M,) : counts per check (6 or 7)
    Accepts mixed forms: 1-based with 0 padding or already 0-based with -1 padding.
    """
    kMN = np.asarray(kMN_in, dtype=int).copy()
    kNM = np.asarray(kNM_in, dtype=int).copy()
    kNRW = np.asarray(kNRW_in, dtype=int).copy()

    # Detect & fix kMN (var->check)
    # Case A: already 0-based with -1 padding (min >= -1 and no zeros that are padding)
    # Case B: 1-based with 0 padding (min >= 0 and many zeros) -> convert: >0 -> -1,  -1 for padding
    if np.min(kMN) >= 0:
        # assume 1-based with 0 padding
        mask_pos = kMN > 0
        kMN[mask_pos] -= 1
        kMN[~mask_pos] = -1  # zeros become -1 padding

    # Detect & fix kNM (check->var)
    if np.min(kNM) >= 0:
        # assume 1-based with 0 padding
        mask_pos = kNM > 0
        kNM[mask_pos] -= 1
        kNM[~mask_pos] = -1

    return kMN, kNM, kNRW

def decode174_91(llr):
    maxiterations = 5

    # Normalize inputs
    llr = np.asarray(llr, dtype=float)
    MN, NM, NRW = _normalize_maps_to_zero_based_with_neg1_padding(kMN, kNM, kNRW)

    # Dimensions (trust the maps, not the imported scalars)
    N = MN.shape[0]           # variables = 174
    M = NM.shape[0]           # checks    = 83
    NRWmax = NM.shape[1]      # 7
    assert len(NRW) == M, "kNRW length mismatch"

    # Precompute: for each variable v, the slot index (0..kNCW-1) of a given check
    # pos_in_var[v, c] = kk or -1 if not connected
    pos_in_var = -np.ones((N, M), dtype=int)
    for v in range(N):
        for kk in range(kNCW):
            c = MN[v, kk]
            if c >= 0:
                pos_in_var[v, c] = kk

    # Messages:
    # toc[e, c] is message variable->check, stored per-check edge slot (edge index e in 0..NRW[c]-1)
    # tanhtoc[e, c] = tanh(-toc/2)
    # tov[kk, v] is message check->variable, stored per-variable slot kk (0..kNCW-1)
    toc     = np.zeros((NRWmax, M), dtype=float)
    tanhtoc = np.zeros((NRWmax, M), dtype=float)
    tov     = np.zeros((kNCW, N), dtype=float)

    # Iterations
    info = []
    for it in range(maxiterations + 1):
        # Aggregate variable beliefs: LLR + sum(check->var msgs)
        zn = llr + tov.sum(axis=0)  # shape (N,)

        # Hard decision and syndrome
        cw = (zn > 0).astype(int)

        ncheck = 0
        # parity for each check: XOR over its neighbors
        for c in range(M):
            deg = NRW[c]
            neigh_vars = NM[c, :deg]
            s = int(np.sum(cw[neigh_vars]) & 1)
            if s:
                ncheck += 1

        info.append(ncheck)
        if ncheck == 0:
            message174 = cw.tolist()
            return message174  # same as your current code (returns 174 bits)

        # ---- Build variable->check messages (toc) ----
        # For each check c and each edge e (variable v at that edge):
        # toc[e,c] = llr[v] + sum_{checks c2 != c connected to v} tov[pos_in_var[v,c2], v]
        for c in range(M):
            deg = NRW[c]
            neigh_vars = NM[c, :deg]
            for e in range(deg):
                v = neigh_vars[e]
                # sum incoming check->var except the recipient check c
                s = llr[v]
                for kk in range(kNCW):
                    c2 = MN[v, kk]
                    if c2 < 0 or c2 == c:
                        continue
                    s += tov[kk, v]
                toc[e, c] = s

        # tanh(-toc/2) (matching your sign convention)
        for c in range(M):
            deg = NRW[c]
            tanhtoc[:deg, c] = np.tanh(-0.5 * toc[:deg, c])

        # ---- Check->variable update (tov) via check-centric product rule ----
        # For each check c and edge e (variable v):
        #   T_e = prod_{e' != e} tanh(-toc[e',c]/2)
        #   msg c->v = 2 * atanh( - T_e )
        for c in range(M):
            deg = NRW[c]
            neigh_vars = NM[c, :deg]
            tvals = tanhtoc[:deg, c]  # length deg
            for e in range(deg):
                # product of all except e
                if deg == 1:
                    Tmn = 0.0
                else:
                    if e == 0:
                        prod = np.prod(tvals[1:])
                    elif e == deg - 1:
                        prod = np.prod(tvals[:-1])
                    else:
                        prod = np.prod(tvals[:e]) * np.prod(tvals[e+1:])
                    Tmn = -prod  # minus sign consistent with tanhtoc = tanh(-toc/2)

                # damped update
                new_val = 2.0 * safe_atanh(np.clip(Tmn, -0.999999999999, 0.999999999999))

                v = neigh_vars[e]
                kk = pos_in_var[v, c]      # slot in v's list where check c lives
                if kk >= 0:
                    alpha = 1.0            # keep your damping hook if you want to tune later
                    tov[kk, v] = alpha * new_val + (1 - alpha) * tov[kk, v]

    # failed to decode
    return []
