import numpy as np
nbits = 5

flip_masks = ((np.arange(1 << nbits)[:, None] >> np.arange(nbits)) & 1).astype(bool)



flip_masks = [f for f in flip_masks if len([1 for b in f if b]) < 3]

for f in flip_masks:
    print(f)
