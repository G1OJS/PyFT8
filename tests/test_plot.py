import matplotlib.pyplot as plt
import pandas as pd

fig, axes = plt.subplots(2,1)
w,p,pi,pl,po,pb,fg,ft = [],[],[],[],[],[],[],[]
with open(f"compare_wsjtx.csv", "r") as f:
    for lfull in f.readlines():
        pdec = lfull[76] != " "
        l = lfull[113:]
#        n = l[1:3]
        n = lfull[108:112]
        n=float(n)
        w.append(n)
        if(pdec):
            p.append(n)
            if(l[0:3]=='I00'): pi.append(n)
            if("L" in l): pl.append(n)
            if("Q" in l): po.append(n)
            if("B" in l): pb.append(n)
        else:
            if("#" in l): fg.append(n)
            if(not "#" in l): ft.append(n)

bins = [300 + 10*b for b in range(30)]

np = len(p)
nt = len(w)
pc = f"{int(100*np/nt)}"

for i in [0,1]:
    axes[i].hist(w, bins = bins, label = "WSJTX", rwidth = 0.4, 
            cumulative = i, color = '#D32F2F', alpha = 1, lw=0.5, edgecolor = "black")
    axes[i].hist(p, bins = bins, label = "PyFT8", rwidth = 1, 
            cumulative = i, color = '#388E3C', alpha = 0.6, lw=0.5, edgecolor = "black")
    axes[i].hist(pi, bins = bins, label = "Immediate", rwidth=0.8,
            cumulative = i, color = 'lime', alpha = 0.6, lw=0.5, edgecolor = "black")
    axes[i].hist(pb, bins = bins, label = "Incl. bit-flips", rwidth=0.5,
            cumulative = i, color = 'orange', alpha = 0.6, lw=0.5, edgecolor = "black")
    axes[i].hist(po, bins = bins, label = "Incl. OSD", rwidth=0.3,
            cumulative = i, color = 'yellow', alpha = 0.6, lw=0.5, edgecolor = "black")
    axes[i].hist(ft, bins = bins, label = "Timeouts", rwidth=0.1,
            cumulative = i, color = 'black', alpha = 1.0, lw=0.2, edgecolor = "black")

    axes[i].set_xlabel("LLR Quality")
    axes[i].set_ylabel(f"Number of decodes{' (cumulative)' if i>0 else ''}")
    fig.suptitle(f"PyFT8 detail vs WSJTX. {nt} decodes, {pc}% to PyFT8")
    axes[i].legend()


plt.tight_layout()
plt.show()
