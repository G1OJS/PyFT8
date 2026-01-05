import matplotlib.pyplot as plt
import pandas as pd

with open ("live_compare.csv","r") as f:
    lines = f.readlines()

fix,ax = plt.subplots()

sync, c, nc = [],[],[]
for l in lines:
    sync.append(float(l[66:71]))
    decoded = "L00" in l or "I00" in l or "B00" in l
    c.append('green' if decoded else 'red')
    nc.append(int(l[76:78]))

ax.scatter(sync,nc, c = c)

plt.tight_layout()
plt.show()
