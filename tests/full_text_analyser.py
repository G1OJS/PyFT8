

with open(r'C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/test_best_baseline.txt', 'r') as f:
    lines = f.readlines()

decode_paths = ['GOOD91', 'LDPC None', 'LDPC CQ', 'LDPC 73', 'LDPC RR73', 'LDPC RRR',
                'OSD demap', 'OSD None', 'OSD CQ', 'OSD 73', 'OSD RR73', 'OSD RRR']
counter = {}
for dp in decode_paths:
    for s in ['grid ', 'fine ']:
        counter.update({s+dp:0})

for l in lines:
    l = l[4:9] + l[21:30].strip()
    l = ' '.join(l.split()[:3])
    counter[l] +=1

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
ax.bar(cats, height = vals)
plt.xticks(
    rotation=45, 
    horizontalalignment='right',
    fontweight='light',
    fontsize='x-large'  
)
plt.tight_layout()
plt.show()

    
