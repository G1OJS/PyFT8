import matplotlib.pyplot as plt
import pandas as pd

fig, ax = plt.subplots( figsize=(10,6))
ws,py,pimm,pl,pba,po,ft = [],[],[],[],[],[],[]


with open(f"compare_wsjtx.csv", "r") as f:
    for lfull in f.readlines():
        pdec = lfull[88] != " "
        l = lfull[110:]
        q = l[0:3]
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

bins = [325 + 5*b for b in range(50)]

np = len(py)
nt = len(ws)
pc = f"{int(100*np/nt)}"

wsjtx = ax.hist(ws, bins = bins,  rwidth = 1.0, label = 'All',
        color = 'grey', alpha = 0.4, lw=1, edgecolor = 'grey')

pyft8 = ax.hist([pimm,pl,pba,po,ft], bins = bins, rwidth = 0.5, 
        stacked = True, alpha = 0.7, lw=1, edgecolor = 'grey',
        color = ['lime','green','orange','yellow','white'])

legwidth = 0.18
wsjtx_legend = ax.legend(handles=[wsjtx[2][0]], 
        loc='upper right', bbox_to_anchor=(1-legwidth,1, legwidth,0), mode='expand',
        title = 'WSJT-X', title_fontproperties = {'weight':'bold', 'size':8}, alignment='left')
ax.add_artist(wsjtx_legend)
ax.legend(handles = pyft8[2],
        labels = ["Immediate","LDPC","BitFlip","OSD","Timeouts"],
        loc = 'upper right', bbox_to_anchor=(1-legwidth,0.9, legwidth,0), mode='expand',
        title = 'PyFT8', title_fontproperties = {'weight':'bold', 'size':8}, alignment='left')


ax.set_xlabel("Signal quality = sum of absolute values of log likelyhood ratios")
ax.set_ylabel(f"Number of decodes")
fig.suptitle(f"PyFT8 vs WSJTX. {nt} decodes, {pc}% to PyFT8")

plt.tight_layout()
plt.show()
