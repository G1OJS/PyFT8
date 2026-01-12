import numpy as np
from itertools import combinations

def gf2_systematic_from_reliability(G, reliab_order):
    G = (G.copy() & 1).astype(np.uint8)
    k, n = G.shape
    colperm = np.array(reliab_order, dtype=np.int64)  
    inv = np.empty(n, dtype=np.int64)
    inv[colperm] = np.arange(n)
    G = G[:, colperm] 
    # Gauss-Jordan:
    row = 0
    for col in range(n):
        if row >= k:
            break
        pivot_rows = np.where(G[row:, col] == 1)[0]
        if pivot_rows.size == 0:
            continue
        piv = row + pivot_rows[0]
        if piv != row:
            G[[row, piv], :] = G[[piv, row], :]
        ones = np.where(G[:, col] == 1)[0]
        for r in ones:
            if r != row:
                G[r, :] ^= G[row, :]
        if col != row:
            G[:, [row, col]] = G[:, [col, row]]
            colperm[[row, col]] = colperm[[col, row]]
        row += 1
    if row < k:
        raise ValueError("Could not find k independent columns to form a systematic generator.")
    return G, colperm

def encode_gf2(u, Gsys):
    u = (u.astype(np.uint8) & 1)
    return (u @ Gsys) & 1

def weighted_distance_bits(c, r_hard, w):
    diff = c ^ r_hard
    return float(np.sum(w * diff))

def osd_decode_minimal(llr_metric, llr_state, G, order=1, L=20):

    llr_metric = np.asarray(llr_metric, dtype=np.float32)
    llr_state  = np.asarray(llr_state,  dtype=np.float32)
    n = llr_metric.size
    k = G.shape[0]
    assert G.shape[1] == n
    # metric (channel)
    r = (llr_metric > 0).astype(np.uint8)
    w = np.abs(llr_metric).astype(np.float32)
    # ordering (decoder state)
    reliab_order = np.argsort(np.abs(llr_state))[::-1]
    Gsys, colperm = gf2_systematic_from_reliability(G, reliab_order)
    r_sys = r[colperm]
    w_sys = w[colperm]
    u0 = r_sys[:k].copy()
    c0_sys = encode_gf2(u0, Gsys)
    best_c_sys = c0_sys.copy()
    best_m = weighted_distance_bits(best_c_sys, r_sys, w_sys)
    info_reliab = w_sys[:k]
    flip_pool = np.argsort(info_reliab)[:min(L, k)]
    for t in range(1, order + 1):
        for comb in combinations(flip_pool, t):
            u = u0.copy()
            u[list(comb)] ^= 1
            c_sys = encode_gf2(u, Gsys)
            m = weighted_distance_bits(c_sys, r_sys, w_sys)
            if m < best_m:
                best_m = m
                best_c_sys = c_sys
    inv = np.empty(n, dtype=np.int64)
    inv[colperm] = np.arange(n)
    best_c_orig = best_c_sys[inv]
    return best_c_orig.astype(np.uint8), best_m


