import matplotlib.pyplot as plt
import pandas as pd

with open ("live_compare.csv","r") as f:
    lines = f.readlines()

fix,ax = plt.subplots()

sync, c, nc = [],[],[]
for l in lines:
    sync.append(float(l[66:71]))
    c.append('green' if "Decoded" in l else 'red')
    nc.append(int(l[90:92]))

ax.scatter(sync,nc, c = c)

plt.tight_layout()
plt.show()
