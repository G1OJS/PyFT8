import numpy as np
from itertools import combinations

def gf2_systematic_from_reliability(G, reliab_order):
    """
    Given generator G (k x n) over GF(2) and a reliability ordering of columns
    (most reliable first), return a systematic form with the first k columns = I
    using ONLY row ops + column swaps.

    Returns:
      Gsys   : (k x n) systematic generator in the permuted column domain
      colperm: length n array mapping sys-domain columns -> original columns
              i.e. original_col = colperm[sys_col]
    """
    G = (G.copy() & 1).astype(np.uint8)
    k, n = G.shape

    # Start by permuting columns by reliability (most reliable first)
    colperm = np.array(reliab_order, dtype=np.int64)  # sys -> original
    inv = np.empty(n, dtype=np.int64)
    inv[colperm] = np.arange(n)
    G = G[:, colperm]  # columns permuted into "reliability domain"

    # Now perform Gauss-Jordan elimination while allowing additional column swaps
    # to ensure we can create an identity in the first k columns.
    row = 0
    for col in range(n):
        if row >= k:
            break

        # We *prefer* pivots earlier (more reliable). Since we're scanning col left->right,
        # this naturally chooses most reliable available pivots.
        pivot_rows = np.where(G[row:, col] == 1)[0]
        if pivot_rows.size == 0:
            continue
        piv = row + pivot_rows[0]

        # Swap pivot row into place
        if piv != row:
            G[[row, piv], :] = G[[piv, row], :]

        # Make column col have a single 1 at row (Gauss-Jordan)
        ones = np.where(G[:, col] == 1)[0]
        for r in ones:
            if r != row:
                G[r, :] ^= G[row, :]

        # If this pivot column isn't already in the "identity block position" row,
        # swap columns so that pivot becomes column 'row' (building I on the left).
        if col != row:
            G[:, [row, col]] = G[:, [col, row]]
            colperm[[row, col]] = colperm[[col, row]]  # keep sys->original mapping aligned

        row += 1

    if row < k:
        raise ValueError("Could not find k independent columns to form a systematic generator.")

    return G, colperm


def encode_gf2(u, Gsys):
    """Encode info bits u (k,) with generator Gsys (k,n): c = u @ Gsys mod 2."""
    u = (u.astype(np.uint8) & 1)
    return (u @ Gsys) & 1


def weighted_distance_bits(c, r_hard, w):
    """
    Weighted Hamming distance between codeword c and received hard bits r_hard:
      sum_i w_i * (c_i xor r_i)
    """
    diff = c ^ r_hard
    return float(np.sum(w * diff))


def osd_decode_minimal(llr, G, order=1, L=20):
    """
    Minimal OSD decoder.
      llr   : (n,) float array (positive => bit 1 more likely)
      G     : (k,n) uint8/bool generator matrix over GF(2)
      order : OSD order (1 or 2 typically)
      L     : how many least reliable *info* positions to consider flipping

    Returns:
      best_codeword_bits (n,) in original column order (0/1)
      best_metric (float) weighted distance
    """
    llr = np.asarray(llr, dtype=np.float32)
    n = llr.size
    k = G.shape[0]
    assert G.shape[1] == n

    # Hard decision + reliabilities
    r = (llr > 0).astype(np.uint8)
    w = np.abs(llr).astype(np.float32)

    # Reliability order: most reliable first
    reliab_order = np.argsort(w)[::-1]

    # Build reliability-aligned systematic generator
    Gsys, colperm = gf2_systematic_from_reliability(G, reliab_order)

    # Move received bits/weights into sys-domain column order
    r_sys = r[colperm]
    w_sys = w[colperm]

    # Baseline info bits are just the hard decisions on the identity positions
    u0 = r_sys[:k].copy()
    c0_sys = encode_gf2(u0, Gsys)

    best_c_sys = c0_sys.copy()
    best_m = weighted_distance_bits(best_c_sys, r_sys, w_sys)

    # Choose which info positions to flip: the least reliable among the k identity positions
    info_reliab = w_sys[:k]
    flip_pool = np.argsort(info_reliab)[:min(L, k)]  # indices within [0..k-1]

    # Trial flips up to given order
    for t in range(1, order + 1):
        for comb in combinations(flip_pool, t):
            u = u0.copy()
            u[list(comb)] ^= 1
            c_sys = encode_gf2(u, Gsys)
            m = weighted_distance_bits(c_sys, r_sys, w_sys)
            if m < best_m:
                best_m = m
                best_c_sys = c_sys

    # Map best codeword back to original column order
    # colperm is sys->original, so we invert it
    inv = np.empty(n, dtype=np.int64)
    inv[colperm] = np.arange(n)
    best_c_orig = best_c_sys[inv]

    return best_c_orig.astype(np.uint8), best_m


