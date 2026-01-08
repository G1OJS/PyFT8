import matplotlib.pyplot as plt
import pandas as pd

with open ("live_compare.csv","r") as f:
    lines = f.readlines()

fix,ax = plt.subplots()

n_its, nc = [],[]
for l in lines:
    decoded = l.find("CRC_passed")
    if(decoded>0):
        n_its.append(len([c for c in l[76:decoded] if c == "L"]))
        nc.append(int(l[68:70]))

ax.hist(nc, bins = range(50), cumulative = -1, density = True)
ax.set_xlabel("Initial ncheck")
ax.set_ylabel("Fraction of decodes (cumulative)")


plt.tight_layout()
plt.show()
