import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
"""
check_ldpc_alignment.py
=======================

Verify structural consistency between the LDPC encoder (generator matrix G)
and decoder (parity-check matrix H) used in FT8 (174,91).

- Builds H from WSJT-X style kMN / kNRW arrays
- Builds G from hex generator rows
- Tests orthogonality: H * G^T ≡ 0 (mod 2)
- Optionally checks reversed/perm-based variants to spot bit-order issues
"""

import numpy as np

from PyFT8.FT8_constants import kMN, kNM, kNRW, kM, kN, kK

def cross_check_nm_mn(kNM, kMN, kNRW, kM, kN):
    ok = True
    for m in range(kM):
        for n in range(kNRW[m]):
            var = kNM[m, n]
            if m not in kMN[var]:
                print(f"Inconsistency: check {m} lists var {var}, but var’s list is {kMN[var]}")
                ok = False
    print("NM–MN cross-consistency:", "OK" if ok else "Mismatch")
    return ok

cross_check_nm_mn(kNM, kMN, kNRW, kM, kN)


# Replace this with your generator hex strings (from WSJT-X encode174_91.f90)
GENERATOR_HEX_ROWS = [
    "8329ce11bf31eaf509f27fc",
    "761c264e25c259335493132",
    "dc265902fb277c6410a1bdc",
    "1b3f417858cd2dd33ec7f62",
    "82f42a1ed9f8a9a96a196f7",
    "f032d2904fc78d5fc9fd45a",
    "3329cf093e9aab2b3926a83",
    "80e40383fd32b760ca802f9",
    "7bfbce5239ff5ff05836b8d",
    "f02a3c48e4f3ee4fba98545",
    "c0150a091ae6177b70b458b",
    "4d53b240c40b447eae8841c",
    "32a6b03e1371e48b97e3129",
    "40486c41b4418a70f9624cc",
    "102b8b19f991e7843dc3a0f",
    "ae2b0b73b08ce334531dc02",
    "ff2e4d8a428e2cfbebf50cd",
    "1b8a83b0c502318da445d10",
    "00b42a35c36a21a77dbfbc5",
    "fead89f5145c1695f31730c",
    "010948f35b8e77b4f2cd78c",
    "be42134f960b31f6b54567b",
    "400ea9de32c3fdb631bde43",
    "efcb6b3b2ee8cdb2e77e9a1",
    "807f520c48ce69a59b1d20c",
    "7a9943a1e4c14e8494a7e56",
    "81f0418f96be4c7e6d64868",
    "782a90a20e2e7273a284e8d",
    "f034d342db9cfd67dc48a49",
    "80e6b5c4b244c1962fb2565",
    "7b60a4b69ec3c745b09de47",
    "7e2801d4ef70d75dbfbf704",
    "00b4b9e40ac2d77bda9b7a5",
    "00bb410688cb53ebbedb19d",
    "fd422d2b3f8a1aefc8c2a3e",
    "030b89cb62a938692d80df3",
    "faef50311a02b2b3e099eb3",
    "fd85b30f42e0d444d4dd73a",
    "fef6b4a2663f07fb406f771",
    "fd4e002e4546f006b8f4241",
    "0052ee477d68fdcd7b239e3",
    "ffe403d050cff2eac82d9a3",
    "0277c049c1c209048442ba4",
    "f9969d536671d4b6b5a078f",
    "7b520e4d3099f26913b7d75",
    "0113d02a61e8c28d8b56d57",
    "f89f4d9f43a428b3a70db60",
    "0245ac63d520b0b5f0816f0",
    "001c89a1974b6f3f57b5985",
    "fd825ac782ce65b528d54da",
    "04b4a254d8ee2f20de0bb7f",
    "ff8c6b5354e89a52f1840b2",
    "01b0f840d2a5c502de80771",
    "fbad903b05b676ab9ed6c03",
    "028449ed2bfc61742d8da08",
    "00f6f030f30db3a7bb61c09",
    "ffa3227b5d54dd6b5a1c387",
    "fcff6061e8efb8d74d8162d",
    "ffaac4f85a5e259960b373f",
    "ff77cc14a2fdab9e4c3aa4d",
    "0174cc14a2fdab9e4c3aa4d",
    "ff35e2f8b0a4e34d68a4047",
    "fc21a2f60c262902d28e456",
    "00b68d7b1c7f38bb5837dc3",
    "fd723f7e8849e947497bf25",
    "02b3f4f153ad03d47fce312",
    "007bd95b28bb16dc1ec1ce5",
    "ff5b97fa052ccddf2b83a28",
    "fdd06a6e095df5378497cf7",
    "ff2cb4f8415e259960b373f",
    "fe0b39b8a8f1718bb58c987",
    "fb407cc11456f9eeb96fbc6",
    "02db0112b14bb2eb4a4c24d",
    "00434a8cb0c31b7da0f3bdf",
    "fe084bbdb43c99bb477cc87",
    "ff6073f1469cf12c2760a9a",
    "fe8b448b0209304c8ab44f6",
    "fb2389ee7a32a0bb99a4727",
    "ff32ee40dc719203ce5f515",
    "0136e5df7f2058ab3541f62",
    "00cc0091ec1508a03784159",
    "fcf722f85db6cdbb2dcaf3c",
    "ff5be30b12cf934b272ec4a",
    "fd6c28a9d8aa9af0f8d7c29",
    "0027b15a4dbf9eab53f9991",
    "00574e2c68aa5b3eeb5a661",
    "00f4a05d48b1359b0a0de21",
    "fc1a4c29a6c3b958eb37d65",
    "fd9cb469f044a7a39bdf751",
    "fc99b05f27a3b2a0d9d83ff",
    "02e0b4ee086c0ef8e423d53",
    "01dbdf8ddba7884bb1b6e32",
    "ff0f4011a4a0b99eb5cf93b",
    "0115df7fe2432b7933e141f"
]

def h_to_systematic(H):
    """Return H_sys, P, Pinv with H*P = [A|I].  P is a column permutation."""
    H = H.copy()
    M, N = H.shape
    P = np.arange(N)
    row = 0
    for col in range(N):
        if row == M:
            break
        # find pivot in/at/after this row
        r = next((r for r in range(row, M) if H[r, col]), None)
        if r is None: 
            continue
        if r != row:
            H[[row, r]] = H[[r, row]]
        # eliminate other 1s in this col
        for rr in range(M):
            if rr != row and H[rr, col]:
                H[rr, :] ^= H[row, :]
        # swap this pivot col into the diagonal position 'row'
        if col != row:
            H[:, [col, row]] = H[:, [row, col]]
            P[[col, row]] = P[[row, col]]
        row += 1

    # After this, H should be [A | I]; the rightmost M columns are identity.
    Pinv = np.empty_like(P)
    Pinv[P] = np.arange(N)
    return H, P, Pinv

def derive_G_from_H(H_sys, P, Pinv, K, N):
    M = H_sys.shape[0]
    # H_sys = [A | I_M] with columns already swapped into that form.
    A = H_sys[:, :K]           # shape M×K
    # Systematic generator in the *systematic* column order:
    G_sys = np.zeros((K, N), dtype=np.uint8)
    G_sys[:, :K] = np.eye(K, dtype=np.uint8)
    G_sys[:, K:] = A.T         # K×M
    # Now un-permute back to the original (decoder) column order:
    G_decoder_order = G_sys[:, Pinv]
    return G_decoder_order


# --- 2. Helper functions ---------------------------------------------------

def bits_from_hex_row(hex_str, N=174, msb_first=True):
    x = int(hex_str, 16)
    bits = np.array([(x >> (N - 1 - i)) & 1 for i in range(N)], dtype=np.uint8) \
            if msb_first else np.array([(x >> i) & 1 for i in range(N)], dtype=np.uint8)
    return bits


def build_H_from_kMN(kMN, kNRW, M, N):
    """
    Build parity-check matrix H (M x N) from zero-based kMN (N x 3) and kNRW (len M).
    kMN[n, :] lists up to 3 check-node indices that bit n connects to.
    """
    H = np.zeros((M, N), dtype=np.uint8)
    for n in range(N):
        for chk in kMN[n]:
            if 0 <= chk < M:
                H[chk, n] = 1
    return H


def mod2_mm(A, B):
    """Matrix multiply mod 2."""
    return (A @ B) & 1


def check_orthogonality(H, G, verbose=True):
    HGt = mod2_mm(H, G.T)
    ok = np.all(HGt == 0)
    if verbose:
        print("Orthogonality:", ok)
        if not ok:
            print("Nonzero elements:", np.sum(HGt))
    return ok


# --- 3. Build matrices -----------------------------------------------------

def main():
    print(f"Building H ({kM}x{kN}) from kMN/kNRW ...")
    H = build_H_from_kMN(kMN, kNRW, kM, kN)

    print(f"Building G ({kK}x{kN}) from generator hex ...")
    G = np.stack([bits_from_hex_row(row, N=kN, msb_first=True) for row in GENERATOR_HEX_ROWS])

    H_sys, P, Pinv = h_to_systematic(H)
    G_from_H = derive_G_from_H(H_sys, P, Pinv, kK, kN)

    print("Check canonical G_from_H against H:", np.all((H @ G_from_H.T) % 2 == 0))


    # WSJT-X colorder array (already 0-based in your paste!)
    colorder = np.array([
      0,1,2,3,28,4,5,6,7,8,9,10,11,34,12,32,13,14,15,16,
     17,18,36,29,43,19,20,42,21,40,30,37,22,47,61,45,44,23,41,39,
     49,24,46,50,48,26,31,33,51,38,52,59,55,66,57,27,60,35,54,58,
     25,56,62,64,67,69,63,68,70,72,65,73,75,74,71,77,78,76,79,80,
     53,81,83,82,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,
    100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,
    120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,
    140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,
    160,161,162,163,164,165,166,167,168,169,170,171,172,173
    ])

    colorder -= 1

    print("Testing H @ G_hex[:, colorder].T ...")
    ok = np.all((H @ (G_from_H[:, colorder]).T) % 2 == 0)
    print("Orthogonality with colorder applied:", ok)

    print("Testing H * G^T ≡ 0 mod 2 ...")
    check_orthogonality(H, G)

    # --- Optional: quick flip tests ---------------------------------------
    print("\nTesting common column flips (diagnostic only):")
    flips = {
        "reverse_all": np.arange(kN - 1, -1, -1),
        "reverse_each_block": np.concatenate((np.arange(kK - 1, -1, -1),
                                              np.arange(kN - 1, kK - 1, -1))),
        "swap_msg_parity": np.concatenate((np.arange(kK, kN), np.arange(0, kK))),
    }
    for name, perm in flips.items():
        ok = check_orthogonality(H, G[:, perm], verbose=False)
        print(f"  {name:<20} → {'OK' if ok else 'fail'}")

    print("\nDone.")


# --------------------------------------------------------------------------
if __name__ == "__main__":
    main()
