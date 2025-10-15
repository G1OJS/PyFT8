import numpy as np
from lib.FT8_ldpc_decode_constants import Nm, Mn

Nm = np.array(Nm, dtype=int)
Mn = np.array(Mn, dtype=int)

# For each column of Nm (each check node)
nrw = np.sum(Nm > 0, axis=1).astype(int)   # one value per check row (83)
# For each column of Mn (each variable node)
ncw = np.sum(Mn > 0, axis=1).astype(int)   # one value per variable column (174)

def get_crc14(m96, length):
    return 0

import numpy as np

def decode174_91_hard(bits_in, maxiterations=30):
    """
    Hard-decision LDPC(174,91) decoder for FT8.
    """

    N, K = 174, 91
    M = N - K
    cw = np.array(bits_in, dtype=np.int8)
    synd = np.zeros(M, dtype=int)
    for iteration in range(maxiterations + 1):
        # --- compute syndromes ---
        ncheck = 0
        for i in range(M):
            synd[i] = 0
            for j in range(nrw[i]):
                synd[i] ^= cw[Nm[i, j] - 1]# XOR (mod 2 sum)
            if synd[i] != 0:
                ncheck += 1

        # --- valid codeword? ---
        if ncheck == 0:
            m96 = np.zeros(96, dtype=np.int8)
            m96[:77] = cw[:77]
            m96[82:96] = cw[77:91]
            nbadcrc = get_crc14(m96, 96)
            if nbadcrc == 0:
                return {
                    "status": "decoded",
                    "message91": cw[:91],
                    "iterations": iteration
                }

        # --- if no CRC success, perform simple bit-flip iteration ---
        if iteration < maxiterations:
            # for each bit, count how many unsatisfied parity checks it participates in
            flip_count = np.zeros(N, dtype=int)
            for j in range(N):
                for i in range(ncw[j]):
                    chk = Mn[j, i]
                    if chk > 0 and synd[chk - 1]:
                        flip_count[j] += 1

            # flip bits involved in many unsatisfied checks (threshold=3 is typical)
            flip_mask = flip_count >= 3
            cw[flip_mask] ^= 1

    return {
        "status": "max_iterations_exceeded",
        "message91": None,
        "iterations": maxiterations
    }

