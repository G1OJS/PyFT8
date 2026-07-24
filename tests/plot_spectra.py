import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator
import pickle


def plot_from_file(ax, fname):
    print(fname)
    with open(fname, 'rb') as f:
        p = pickle.load(f)
        im = ax.imshow(p, origin = 'lower')

fig, ax = plt.subplots(figsize = (9,9))
ax.yaxis.set_label_position("right")


plot_from_file(ax, '../PyFT8/Spec0001.pkl')

plt.show()
