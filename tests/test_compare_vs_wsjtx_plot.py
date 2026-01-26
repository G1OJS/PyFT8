import matplotlib.pyplot as plt
import pandas as pd


with open(f"data/compare_wsjtx.csv", "r") as f:
    lines=f.readlines()

py      = [[],              [],             [],         [],         [],                 [],         [],         []          ]
pycols  = ['black',         'lime',         'yellow',   'orange',   'teal',             'green',    'white',    'red'       ]
pylabs  = ['Hard t+8 sec',  'Immediate',    'OSD2',     'OSD1',     'LDPC &Bitflip',    'LDPC',     'Timeouts', 'Incorrect' ]
substrs = ['H00',           'I00',          'P00'       'O00',      'A',                'L']

print(len(py))
print(len(pycols))
print(len(pylabs))
print(len(substrs))

bins = [350 + 5*b for b in range(50)]

ws = [[],[]]
pydecs = 0
for lfull in lines:
    Hz, cofreq, q, nc, flags, dpath = lfull.split(",")
    q = int(q)
    if(not "#" in dpath): py[6].append(q)
    if("C00#" in dpath):
        for i, s in enumerate(substrs):
            if(s in dpath):
                py[i].append(q)
                break
        if (not "i" in flags):
            pydecs +=1
        if("i" in flags):
            py[7].append(q)
  
    if('cofreq' in cofreq):
        ws[1].append(q)
    else:
        ws[0].append(q)


fig, ax = plt.subplots( figsize=(10,6))
wsjtx = ax.hist(ws, bins = bins,  rwidth = 1.0, label = 'All',
        stacked = True, color = ['green', 'orange'], alpha = 0.2, lw=2, edgecolor = 'grey')

pyft8 = ax.hist(py, bins = bins, rwidth = 0.5, 
        stacked = True, alpha = 0.7, lw=1, edgecolor = 'grey', color = pycols)

legwidth = 0.18
wsjtx_legend = ax.legend(handles=[wsjtx[2][0], wsjtx[2][1]], labels = ['isolated','ovelapping'],
        loc='upper right', bbox_to_anchor=(1-legwidth,1, legwidth,0), mode='expand',
        title = 'WSJT-X', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
ax.add_artist(wsjtx_legend)
ax.legend(handles = pyft8[2], labels = pylabs,
        loc = 'upper right', bbox_to_anchor=(1-legwidth,0.85, legwidth,0), mode='expand',
        title = 'PyFT8', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')

ax.set_xlabel("Signal quality = sum of absolute values of log likelyhood ratios")
ax.set_ylabel(f"Number of decodes")

ntot = len(lines)
py_pc = f"{int(100*pydecs/ntot)}"
pyh_pc = f"{int(100*len(py[0])/ntot)}"
fig.suptitle(f"PyFT8 vs WSJTX. {ntot} decodes, {py_pc}% correct to PyFT8 ({pyh_pc}% using hard decode only)")

plt.tight_layout()
plt.show()
