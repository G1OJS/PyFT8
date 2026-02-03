import matplotlib.pyplot as plt
import pickle

def plot_success(fig, ax, load_file):

    with open("results/data/compare_data.pkl", "rb") as f:
        d = pickle.load(f)
    decodes = d['decodes']
    params = d['params']

    if not any(decodes):
        return
    
    py =        [[],[],[],[],[],[]]
    pycols  =   ['lime', 'green', 'yellow', 'red', '#c0e7fa', '#ebf6fa']
    pylabs  =   ['Immediate', 'LDPC', 'OSD', 'ERR', 'Stall', 'Timeout' ]
    ws =        [[],[]]
    wcols =     ['#141700','#664b07']
    wlabs =     ['isolated','overlapping']

    bins = [0.4 + 0.1*b for b in range(25)]
    
    for w, p in decodes:
        q = p['llr0_sd']

        if(w['msg'] != ''):
            if(w['cofreq']):
                ws[1].append(q)
            else:
                ws[0].append(q)

        if(p['msg'] != ''):
            if(p['msg'] == w['msg'] or w['msg'] == ''):
                if("O00" in p['decode_path']):
                    py[2].append(q)
                elif ("L00" in p['decode_path']):
                    py[1].append(q)
                else:
                    py[0].append(q)
            else:
                py[3].append(q)
        elif('_' in p['decode_path']):
            py[4].append(q)
        elif('#' not in p['decode_path']):
            py[5].append(q)                

    ax.cla()

    dict_2 = ax.hist(ws, bins = bins,  rwidth = 1.0, label = 'All',
            stacked = True, color = wcols, alpha = 0.4, lw=0.5, edgecolor = 'grey')

    pyft8 = ax.hist(py, bins = bins, rwidth = 0.45, 
            stacked = True, alpha = 0.7, lw=.5, edgecolor = 'grey', color = pycols)

    legwidth = 0.18
    dict_2_legend = ax.legend(handles = dict_2[2], labels = wlabs,
            loc='upper right', bbox_to_anchor=(1-legwidth,1, legwidth,0), mode='expand',
            title = "WSJT-X", title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
    ax.add_artist(dict_2_legend)
    pyft8_legend = ax.legend(handles = pyft8[2], labels = pylabs,
            loc = 'upper right', bbox_to_anchor=(1-legwidth,0.85, legwidth,0), mode='expand',
            title = 'PyFT8', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
    ax.add_artist(pyft8_legend)

    ax.set_xlabel("Signal quality = sigma(llr)")
    ax.set_xlim(bins[0],bins[-1])
    ax.set_ylabel(f"Number of decodes")

    wdecs = len(ws[0]) + len(ws[1])
    pydecs = len(py[0])+len(py[1])+len(py[2])+len(py[3])
    pydecs_corr = pydecs - len(py[3])
    pycorr_pc = f"{int(100*pydecs_corr/wdecs)}"
    pytot_pc = f"{int(100*pydecs/wdecs)}"
    fig.suptitle(f"PyFT8 {pydecs} vs WSJT-X {wdecs} decodes, {pytot_pc}% ({pycorr_pc}% correct) to PyFT8")
    if(params):
        params1 = dict(list(params.items())[:len(params)//2])
        params2 = dict(list(params.items())[len(params)//2:])
        plt.text(0,1.05, params1, fontsize = 6, transform = ax.transAxes)
        plt.text(0,1.02, params2, fontsize = 6, transform = ax.transAxes)
    plt.savefig("results/compare_results.png")
