import numpy as np

N = 10
pats = []
pat0 = np.zeros(N, dtype = np.uint8)
for i in range(N):
    pats.append([i])
    
for i in range(1, N):
    for j in range(i):
        pats.append([i,j])

for i in range(1, N):
    for j in range(i):
        for k in range(j):
            pats.append([i,j,k])

for p in pats:
    print(p)

print("")
print(len(pats))

import pickle
with open('osdpats.pkl','wb') as f:
    pickle.dump(pats, f)
