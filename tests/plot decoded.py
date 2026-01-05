import matplotlib.pyplot as plt
import pandas as pd

with open ("live_compare.csv","r") as f:
    lines = f.readlines()

fix,ax = plt.subplots()

n_its, nc = [],[]
for l in lines:
    decoded = l.find("L00")
    if(decoded>0):
        n_its.append(len([c for c in l[76:decoded] if c == "L"]))
        nc.append(int(l[76:78]))

#ax.scatter(nc,n_its)

ax.hist(n_its, bins = range(25))
ax.set_xlabel("Number of iterations")
ax.set_ylabel("Number of decodes")

plt.tight_layout()
plt.show()
