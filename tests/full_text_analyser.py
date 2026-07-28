

with open('live_decode_times_PyFT8_8_28_baseline.txt', 'r') as f:
    lines = f.readlines()

decode_paths = ['GOOD91', 'LDPC_NoAP', 'LDPC_CQ', 'LDPC_73', 'LDPC_RR73', 'LDPC_RRR',
                'OSD_demap', 'OSD_NoAP', 'OSD_CQ', 'OSD_73', 'OSD_RR73', 'OSD_RRR']
counter = {}
for s in ['grid_', 'fine_']:
    for dp in decode_paths:
        counter.update({s+dp:0})

for l in lines:
    cat = l.split()[1]
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

    
