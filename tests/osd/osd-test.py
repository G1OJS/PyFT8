import numpy as np
from itertools import combinations

generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)

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
        for bits in ones:
            if bits != row:
                G[bits, :] ^= G[row, :]
        if col != row:
            G[:, [row, col]] = G[:, [col, row]]
            colperm[[row, col]] = colperm[[col, row]]
        row += 1
    if row < k:
        raise ValueError("Could not find k independent columns to form a systematic generator.")
    return G, colperm

def encode_and_score(u, Gsys, bits_sys, vals_sys):
    u = (u.astype(np.uint8) & 1)
    codeword = (u @ Gsys) & 1
    bit_diff = codeword ^ bits_sys
    score = float(np.sum(vals_sys * bit_diff))
    return codeword, score

K, N = 91, 174
def osd_decode_minimal(llr, reliab_order, Ls = [30]):

    # determine colperm ordering and inverse
    Gsys, colperm = gf2_systematic_from_reliability(G, reliab_order)
    colperm_inv = np.empty(N, dtype=np.int64)
    colperm_inv[colperm] = np.arange(N)

    # permute bits and strengths to new order
    llr_sys = llr[colperm]
    bits_sys, vals_sys = (llr_sys > 0).astype(np.uint8), np.abs(llr_sys)
    bits_sys91, vals_sys91 = bits_sys[:K], vals_sys[:K]

    best  = ([], 1e20)
    for t in range(1, len(Ls) + 1):
        flip_pool = np.argsort(vals_sys91)[:min(Ls[t-1], K)]
        for comb in combinations(flip_pool, t):
            bits91_test = bits_sys91.copy()
            bits91_test[list(comb)] ^= 1
            test = encode_and_score(bits91_test, Gsys, bits_sys, vals_sys)
            if test[1] < best[1]:
                best = test

    return best[0][colperm_inv].astype(np.uint8)


def check_G():
    from PyFT8.cycle_manager import Candidate
    u = np.random.randint(0, 2, size=91, dtype=np.uint8)
    c = (u @ G) & 1
    cand = Candidate()
    cand.llr = np.where(c == 1, +1.0, -1.0)
    assert cand.ldpc.calc_ncheck(self.llr) == 0

def print_input_state(llr, cw):
    llr_bits = 1*(llr>0)
    print(llr_bits)
    print()
    print(cw)
    print()
    print(msg_tuple)
    print()
    errs = llr_bits ^ cw
    print(errs[:78])
    print(errs[78:93])
    print(errs[93:])

import pickle
with open('osd.pkl', 'rb') as f:
    llr, cw, msg_tuple = pickle.load(f)

rel_ord = np.argsort(np.abs(llr))[::-1]
cw = osd_decode_minimal(llr, rel_ord)
bits91_int = 0
for bit in (cw[:91] > 0).astype(int).tolist():
    bits91_int = (bits91_int << 1) | bit
from PyFT8.receiver import check_crc
bits77_int = check_crc(bits91_int)
if bits77_int:
    print("Success")
