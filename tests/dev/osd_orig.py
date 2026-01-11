import numpy as np
from itertools import combinations

generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)

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

