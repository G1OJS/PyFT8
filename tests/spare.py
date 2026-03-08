import numpy as np
import matplotlib.pyplot as plt
import pickle

with open('loop_scores.pkl', 'rb') as f:
    ls = pickle.load(f)

with open('vector_scores.pkl', 'rb') as f:
    vs = pickle.load(f)

fig, axs = plt.subplots(3,1, figsize = (8,10))
vx = 100
vm = 30
im0 = axs[0].imshow(ls, vmax = vx, vmin = vm, aspect = 4, origin = 'lower')
im1 = axs[1].imshow(vs,vmax = vx, vmin = vm, aspect = 4, origin = 'lower')
im = axs[2].imshow(vs[:100, :980] - ls[:100, :980], aspect = 4, vmax = 40, vmin = -40, origin = 'lower')
plt.tight_layout()
plt.show()
