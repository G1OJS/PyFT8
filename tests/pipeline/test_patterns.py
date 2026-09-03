import numpy as np


chbits91 = np.zeros(91, dtype = np.uint8)
cnt = 0
for j in range(-1, 8):
    imax = [9,9,9,9,9,9,9,9,91][j]
    for i in range(j, imax):
        bits91 = chbits91.copy()
        if j >= 0:
            bits91[j] ^= 1
        if i != j:
            bits91[i] ^= 1
        print(f"{cnt:05d} {i:02d} {j:02d} {''.join([str(b) for b in bits91])}")
        cnt += 1

