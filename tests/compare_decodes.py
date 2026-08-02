import numpy as np
import matplotlib.pyplot as plt

with open('wsjtx_8_28_FAST.txt') as f:
    ws = f.readlines()

t1 = float(ws[0].split()[2])
i1 = 0
ws_cycles = []
for i, row in enumerate(ws):
    fields = row.split()
    t2 = float(fields[2])
    if (t2-t1 > 5):
        ws_cycles.append([' '.join(r.split()[3:]) for r in ws[i1:i]])
        i1 = i
    t1 = t2

with open('PyFT8.txt') as f:
    py = f.readlines()

t1 = float(py[0].split()[2])
i1 = 0
py_cycles = []
for i, row in enumerate(py):
    fields = row.split()
    t2 = float(fields[2])
    if (t2-t1 > 5):
        py_cycles.append([' '.join(r.split()[9:]) for r in py[i1:i]])
        i1 = i
    t1 = t2

def match2(a, b):
    aparts = a.split()
    bparts = b.split()
    if len(aparts) == 2 and len(bparts) == 2:
        return aparts == bparts 
    if len(aparts) == 3 and len(bparts) == 3:
        return aparts == bparts or (aparts[2]==bparts[2] and (aparts[0]==bparts[0] or aparts[1]==bparts[1]))

p_only, w_only = 0, 0
for i, pc in enumerate(py_cycles):
    wc = ws_cycles[i]
    print(f"Cycle {i} =====================================")
    for p in pc:
        if not any([match2(p, w) for w in wc]):
            print(f"PyFT8 only: {p}")
            p_only += 1
    for w in wc:
        if not any([match2(w, p) for p in pc]):
             #print(f"WSJTx only: {w}")
             w_only += 1

print(f"Total PyFT8-only: {p_only}")
print(f"Total WSJTX-only: {w_only}")
    
