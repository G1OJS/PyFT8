import pickle as pkl
import matplotlib.pyplot as plt
import numpy as np

with open ('cand_637.pkl', 'rb') as f:
    cgrid = pkl.load(f)

fig, ax = plt.subplots()

#ax.imshow(np.abs(cgrid))

for fbin_idx in range(8):
    ax.plot(np.angle(cgrid[0:20,3*fbin_idx+1]))
plt.show()
