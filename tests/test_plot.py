import matplotlib.pyplot as plt
import pandas as pd

fig, axes = plt.subplots( figsize=(10,6))
ws,py,pimm,pl,pba,pbb,po,pp,ft = [],[],[],[],[],[],[],[],[]

with open(f"compare_wsjtx.csv", "r") as f:
    for lfull in f.readlines():
        pdec = lfull[88] != " "
        l = lfull[119:]
        q = l[0:5]
        q=float(q)
        ws.append(q)
        if(pdec):
            py.append(q)
            if('I00' in l): pimm.append(q)
            if("L" in l): pl.append(q)
            if("A" in l): pba.append(q)
            if("O" in l): po.append(q)
        else:
            if(not "#" in l): ft.append(q)

bins = [350 + 10*b for b in range(20)]

np = len(py)
nt = len(ws)
pc = f"{int(100*np/nt)}"

axes.hist(ws, bins = bins, label = "WSJTX", rwidth = 0.4, 
        color = 'grey', alpha = 1, lw=0.5, edgecolor = "black")
axes.hist(py, bins = bins, label = "PyFT8", rwidth = 1, 
        color = '#388E3C', alpha = 1, lw=0.5, edgecolor = "black")

axes.hist(pimm, bins = bins, label = "Imm", rwidth=1,
        color = 'lime', alpha = 0.6, lw=0.5, edgecolor = "black")

axes.hist(pl, bins = bins, label = "LDPC", rwidth=0.8,
        color = 'orange', alpha = 0.8, lw=0.5, edgecolor = "black")
axes.hist(pba, bins = bins, label = "BitFlipA", rwidth=0.6,
        color = 'blue', alpha = 0.8, lw=0.5, edgecolor = "black")
axes.hist(po, bins = bins, label = "OSD", rwidth=0.4,
        color = 'white', alpha = 0.8, lw=0.5, edgecolor = "black")


axes.hist(ft, bins = bins, label = "Timeouts", rwidth=0.1,
        color = 'red', alpha = 1.0, lw=0.2, edgecolor = "red")

axes.set_xlabel("LLR Quality")
axes.set_ylabel(f"Number of decodes")

fig.suptitle(f"PyFT8 detail vs WSJTX. {nt} decodes, {pc}% to PyFT8")
axes.legend(loc='upper left')

plt.tight_layout()
plt.show()
