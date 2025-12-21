import matplotlib.pyplot as plt
import pandas as pd

with open('live_compare_rows_2_vs FAST.csv','r') as f:
    lines = f.readlines()

tW, tP = [],[]
for l in lines:
    t = l.split()
    D,P,W = t[4], t[5], t[6]
    if (D=='BOTH' or D=="WSJTX"):
        tW.append((float(W) +7) %15 -7)

plt.scatter(tW, tW)
    

plt.show()
