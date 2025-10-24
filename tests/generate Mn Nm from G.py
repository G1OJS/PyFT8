import numpy as np
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.FT8_constants import kMN, kNM, kNRW, kM, kN, kK, kGEN

K,M,N = kK, kM, kN

G_ints = kGEN

# ---- unpack A^T (83 columns of 91 bits) ----
A_T = np.zeros((K, M), dtype=np.uint8)
for i, word in enumerate(G_ints):
    for bit in range(K):
        A_T[bit, i] = (word >> bit) & 1

# ---- build A (83×91) and H = [A | I] ----
A = A_T.T
H = np.zeros((M, N), dtype=np.uint8)
H[:, :K] = A
H[:, K:] = np.eye(M, dtype=np.uint8)

# ---- derive kMN, kNM, kNRW ----
kMN = np.full((N, 3), -1, dtype=int)
for n in range(N):
    rows = np.flatnonzero(H[:, n])
    if len(rows) != 3:
        print(f"Column {n} weight = {len(rows)}")  # debugging only
    kMN[n, :len(rows)] = rows

kNM = np.full((M, 7), -1, dtype=int)
kNRW = np.zeros(M, dtype=int)
for m in range(M):
    cols = np.flatnonzero(H[m, :])
    kNRW[m] = len(cols)
    kNM[m, :len(cols)] = cols

print("H·G^T == 0 ?",
      np.all((H @ np.vstack([np.eye(K, dtype=np.uint8), A]) % 2).T == 0))

print("Column weights:", np.unique(H.sum(axis=0)))
print("Row weights:", np.unique(H.sum(axis=1)))
print("Shapes: kMN", kMN.shape, "kNM", kNM.shape)

