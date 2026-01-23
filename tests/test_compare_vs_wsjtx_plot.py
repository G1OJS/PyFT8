import matplotlib.pyplot as plt
import pandas as pd


with open(f"data/compare_wsjtx.csv", "r") as f:
    lines=f.readlines()

pycols = ['lime','green','orange','yellow','white']
pylabs = ["Immediate","LDPC","LDPC & BitFlip","OSD","Timeouts"]
bins = [350 + 5*b for b in range(60)]

py = [[],[],[],[],[]]
ws = []
pydecs = 0
min_sig = 90
for lfull in lines:
    fields = lfull.split(",")
    sig, sd, q, nc, dpath = float(fields[0]), float(fields[1]),float(fields[2]), int(fields[3]), fields[4]
    q = sig
    if("C00#" in dpath):
        if('H00' in dpath and sig < min_sig): min_sig = sig
        pydecs +=1
        if('H00' in dpath or 'I00' in dpath):
            py[0].append(q)
        elif('O00' in dpath):
            py[3].append(q)
        elif('A' in dpath):
            py[2].append(q)
        elif('L' in dpath):
            py[1].append(q)
            
    if(not "#" in dpath): py[4].append(q)
    ws.append(q)

fig, ax = plt.subplots( figsize=(10,6))
wsjtx = ax.hist(ws,  rwidth = 1.0, label = 'All',
        color = 'grey', alpha = 0.4, lw=1, edgecolor = 'grey')

pyft8 = ax.hist(py,rwidth = 0.5, 
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

print(f"Min sig for hard decode = {min_sig}")

plt.tight_layout()
plt.show()
