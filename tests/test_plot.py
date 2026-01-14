import matplotlib.pyplot as plt
import pandas as pd


with open(f"compare_wsjtx.csv", "r") as f:
    lines=f.readlines()

pycols = ['lime','green','orange','yellow','white']
pylabs = ["Immediate","LDPC","LDPC & BitFlip","OSD","Timeouts"]
bins = [325 + 5*b for b in range(50)]

py = [[],[],[],[],[]]
ws = []
pydecs = 0
for lfull in lines:
    l = lfull[110:]
    q = l[0:3]
    q=float(q)
    if(lfull[88] != " "):
        pydecs +=1
        if('I00' in l):
            py[0].append(q)
        elif('O00' in l):
            py[3].append(q)
        elif('A' in l):
            py[2].append(q)
        elif('L' in l): py[1].append(q)
            
    if(not "#" in l): py[4].append(q)
    ws.append(q)

fig, ax = plt.subplots( figsize=(10,6))
wsjtx = ax.hist(ws, bins = bins,  rwidth = 1.0, label = 'All',
        color = 'grey', alpha = 0.4, lw=1, edgecolor = 'grey')

pyft8 = ax.hist(py, bins = bins, rwidth = 0.5, 
        stacked = True, alpha = 0.7, lw=1, edgecolor = 'grey', color = pycols)

legwidth = 0.18
wsjtx_legend = ax.legend(handles=[wsjtx[2][0]], 
        loc='upper right', bbox_to_anchor=(1-legwidth,1, legwidth,0), mode='expand',
        title = 'WSJT-X', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
ax.add_artist(wsjtx_legend)
ax.legend(handles = pyft8[2], labels = pylabs,
        loc = 'upper right', bbox_to_anchor=(1-legwidth,0.9, legwidth,0), mode='expand',
        title = 'PyFT8', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')

ax.set_xlabel("Signal quality = sum of absolute values of log likelyhood ratios")
ax.set_ylabel(f"Number of decodes")

ntot = len(ws)
py_pc = f"{int(100*pydecs/ntot)}"
fig.suptitle(f"PyFT8 vs WSJTX. {ntot} decodes, {py_pc}% to PyFT8")

plt.tight_layout()
plt.show()
