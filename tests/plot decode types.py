

file = "PyFT8.txt"
#file = "PyFT8_8_28_baseline.txt"

with open(file, 'r') as f:
    lines = f.readlines()


counter = {}

for l in lines:
    cat = l.split()[3]
    if cat not in counter:
        counter[cat]=0
    counter[cat] +=1

catvals = []
for c in counter.keys():
    catvals.append((c, counter[c]))
#catvals.sort(key = lambda cv: cv[1])

cats, vals = [], []
for c in catvals:
    if(c[1]>0):
        cats.append(c[0])
        vals.append(c[1])

import matplotlib.pyplot as plt
fig, ax = plt.subplots()
bars = ax.bar(cats, height = vals)
ax.bar_label(bars, padding=3)
plt.xticks(
    rotation=45, 
    horizontalalignment='right',
    fontweight='light',
    fontsize='x-large'  
)
plt.tight_layout()
plt.show()

    
