import matplotlib.pyplot as plt
import pandas as pd
import pickle
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

global wsjtx_dicts, pyft8_cands, new_matches, cands_matched, historic_matches, do_analysis, params
wsjtx_dicts = []
pyft8_cands = []
new_matches = None
cands_matched = []
historic_matches = []
do_analysis = False

def plot_success(fig, ax, load_file = False):
    global historic_matches, params

    if(load_file):
        with open("results/data/compare_data.pkl", "rb") as f:
            d = pickle.load(f)
        historic_matches = d['matches']
        params = d['params']

    if not any(historic_matches):
        return
    
    py =      [[],[],[],[],[],[]]
    pycols  = ['lime', 'green', 'yellow', 'red', 'orange', 'white']
    pylabs  = ['OK', 'OK-LDPC', 'OK-OSD', 'ERR', 'Stall', 'Timeout' ]

    bins = [0 + 0.1*b for b in range(40)]
    
    ws = [[],[]]
    for w, c in historic_matches:
        q = c.llr0_sd

        if(w['cofreq']):
            ws[1].append(q)
        else:
            ws[0].append(q)

        if(c.msg):
            if(' '.join(c.msg) == w['msg']):
                if("O00" in c.decode_path or "P00" in c.decode_path or "Q00" in c.decode_path):
                    py[2].append(q)
                elif ("L00" in c.decode_path):
                    py[1].append(q)
                else:
                    py[0].append(q)
            else:
                py[3].append(q)
        elif('#' in c.decode_path):
            py[4].append(q)
        else:
            py[5].append(q)                

    if(len(py[0]) ==0):
        return

    ax.cla()

    wsjtx = ax.hist(ws, bins = bins,  rwidth = 1.0, label = 'All',
            stacked = True, color = ['green', 'orange'], alpha = 0.4, lw=0.5, edgecolor = 'grey')

    pyft8 = ax.hist(py, bins = bins, rwidth = 0.5, 
            stacked = True, alpha = 0.7, lw=.4, edgecolor = 'grey', color = pycols)
    
    legwidth = 0.18
    wsjtx_legend = ax.legend(handles = wsjtx[2], labels = ['isolated','ovelapping'],
            loc='upper right', bbox_to_anchor=(1-legwidth,1, legwidth,0), mode='expand',
            title = 'WSJT-X', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
    ax.add_artist(wsjtx_legend)
    pyft8_legend = ax.legend(handles = pyft8[2], labels = pylabs,
            loc = 'upper right', bbox_to_anchor=(1-legwidth,0.85, legwidth,0), mode='expand',
            title = 'PyFT8', title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
    ax.add_artist(pyft8_legend)

    ax.set_xlabel("Signal quality = sigma(llr)")
    ax.set_xlim(bins[0],bins[-1])
    ax.set_ylabel(f"Number of decodes")

    wdecs = len(ws[0]) + len(ws[1])
    pydecs = len(py[0])+len(py[1])+len(py[2])
    pydecs_corr = pydecs - len(py[3])
    pycorr_pc = f"{int(100*pydecs_corr/wdecs)}"
    pytot_pc = f"{int(100*pydecs/wdecs)}"
    fig.suptitle(f"PyFT8 {pydecs} vs WSJTX. {wdecs} decodes, {pytot_pc}% ({pycorr_pc}% correct) to PyFT8")
  #  params1 = dict(list(params.items())[:len(params)//2])
  #  params2 = dict(list(params.items())[len(params)//2:])
  #  plt.text(0,1.05, params1, fontsize = 6, transform = ax.transAxes)
  #  plt.text(0,1.02, params2, fontsize = 6, transform = ax.transAxes)
    plt.savefig("compare_results.png")

def wsjtx_all_tailer(all_file, cycle_manager):
    global wsjtx_dicts
    print(f"Following {all_file}")
    
    def follow():
        with open(all_file, "r") as f:
            f.seek(0, 2)
            while cycle_manager.running:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()
    for line in follow():
        ls = line.split()
        decode_dict = False
        try:
            cs, freq, dt, snr = ls[0], int(ls[6]), float(ls[5]), int(ls[4])
            msg = f"{ls[7]} {ls[8]} {ls[9]}"
            wsjtx_dicts.append({'cs':cs,'f':int(freq),'msg':msg, 'dt':dt,'snr':snr,'td': f"{time.time() %60:4.1f}"})
        except:
            print(f"Wsjtx_tailer error in line '{line}'")

def get_wsjtx_decodes(wav_decodes_file):
    global wsjtx_dicts
    with open(wav_decodes_file,'r') as f:
        lines = f.readlines()
    for l in lines:
        wsjtx_dicts.append({'cs':'000000_000000', 'f':int(l[16:21]), 'msg':l[24:].strip(), 'snr':int(l[8:11]), 'dt':float(l[12:16]), 'td':''})

def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

def onCandidateRollover(candidates):
    global pyft8_cands, do_analysis
    pyft8_cands = candidates.copy()
    do_analysis = True

def analyse_dictionaries(fig_s, ax_s):
    global cands_matched, new_matches
    time.sleep(5)

    new_matches = [(w, c) for w in wsjtx_dicts for c in pyft8_cands if abs(w['f'] - c.fHz) < 3
               and (w['cs'] == c.cyclestart_str or w['cs']=='000000_000000')]
    
    best = {}
    for w, c in new_matches:
        key = (w['cs'], w['msg'])
        has_message = True if c.msg else False
        score = (has_message, c.llr0_sd)
        if key not in best or score > best[key][0]:
            best[key] = (score, w, c)
    new_matches = [(w, c) for (_, w, c) in best.values()]

    wsjtx_cofreqs = [w['f'] for w,c in new_matches for w2,c in new_matches if 0 <= np.abs(w['f'] - w2['f']) <= 51 and ''.join(w['msg']) != ''.join(w2['msg'])]

    pyft8 = [c for c in pyft8_cands if c.msg]
    pyft8_msgs = [c.msg for c in pyft8]
    pyft8 = [c for c in pyft8 if c.msg not in pyft8_msgs]
    wsjtx_msgs = [w['msg'] for w in wsjtx_dicts]
    pyft8_only = [c for c in pyft8 if ' '.join(c.msg) not in wsjtx_msgs]

    new_matches.sort(key = lambda tup: tup[1].fHz)
    unique = set()
    print(f"{'Cycle start':<13} {'fHzW':<4} {'cofreq':<6} {'fHzP':<4} {'snrW':<3} {'snrP':<3} {'dtW':<4} {'dtP':<4} {'tdW':<4} {'tdP':<4}"
              +f"{'msgW':<23} {'msgP':<23} {'llrSD':<4} {'decode_history'}")
    for w, c in new_matches:
        cands_matched.append(c)
        td = f"{c.decode_completed %60:4.1f}" if c.decode_completed else '     '
        w.update({'cofreq': w['f'] in wsjtx_cofreqs})
        msg = ' '.join(c.msg) if c.msg else ''   
        cofreq = 'cofreq' if w['cofreq'] else "  --  "
        basics = f"{w['cs']} {w['f']:4d} {cofreq} {c.fHz:4d}{w['snr']:+04d} {c.snr:+04d} {w['dt']:4.1f} {c.dt:4.1f} {w['td']:<4} {td:<4}"
        if(msg !=''): unique.add(msg)
        print(f"{basics} {w['msg']:<23} {msg:<23} {c.llr0_sd:04.2f} {c.decode_path}")
        historic_matches.append((w,c))
    for c in pyft8_only:
        basics = f"{c.cyclestart_str} {c.fHz:4d} {"  --  "} {c.fHz:4d} {c.snr:+03d} {c.snr:+03d} {c.dt:4.1f} {c.dt:4.1f} {0} {0}"
        msg = ' '.join(c.msg) if c.msg else ''

    print(f"{len(unique)} unique decodes")
    if(not len(unique)):
        print("Is WSJT-X running??")
    unprocessed = [c for w, c in new_matches if not "#" in c.decode_path]
    if(len(unprocessed)):
        best_unprocessed_quality = np.max([c.llr0_sd for c in unprocessed])
        best_unprocessed_ncheck0 = np.min([c.ncheck0 for c in unprocessed])
        print(f"{len(unprocessed)} unprocessed candidates decoded by wsjt-x, best qual {best_unprocessed_quality:4.2f} best ncheck0 {best_unprocessed_ncheck0}")
    if(show_success_plot):
        plot_success(fig_s, ax_s)
        plt.pause(0.1)

    params = None
    with open("results/data/compare_data.pkl","wb") as f:
        pickle.dump({'matches':historic_matches, 'params':params}, f)
    
def calibrate_snr():
    import matplotlib.pyplot as plt
    fix, ax = plt.subplots()
    x,y = [],[]
    for w, c in new_matches:
        x.append(c.snr)
        y.append(float(w['snr']))
    ax.plot(x,y)
    plt.show()

def onDecode(c):
  #  print(c.fHz, c.msg)
    pass

def show_matched_cands(dBrange = 30):
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    
    if not len(cands_matched): return

    n = len(cands_matched)
    fig, axs = plt.subplots(1, n, figsize = (15, 5))
    for i, c in enumerate(cands_matched):
        if(c.p_dB is not None):
            p = c.p_dB
            p = np.clip(p, np.max(p) - dBrange, None)
            axs[i].imshow(p, origin="lower", aspect="auto", 
                      cmap="inferno", interpolation="none", alpha = 0.8)       
            axs[i].xaxis.set_major_locator(ticker.NullLocator())
            axs[i].yaxis.set_major_locator(ticker.NullLocator())
            axs[i].set_ylabel(f"{c.msg}", fontsize=8)
    plt.tick_params(labelleft=False)
    plt.tight_layout()
    plt.show()

            
def compare(dataset, freq_range, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"):
    global do_analysis

    if(dataset):
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, test_speed_factor = 1, max_cycles = 2, 
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,  
                                      audio_in_wav = dataset+".wav", verbose = True)
        get_wsjtx_decodes(dataset+".txt")
    else:
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None,
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range, 
                                      input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
        threading.Thread(target=wsjtx_all_tailer, args = (all_file,cycle_manager,)).start()

    fig_s, ax_s = None, None
    if(show_success_plot):
        fig_s, ax_s = plt.subplots( figsize=(10,6))
        plt.ion()
    if(show_waterfall):
        fig, axs = plt.subplots(figsize = (20,7))
        plt.ion()
        plt.tight_layout()
        waterfall = None
    try:
        while cycle_manager.running:
            time.sleep(1)
            if(show_waterfall):
                p = cycle_manager.spectrum.audio_in.pgrid_main
                pmax = np.max(p)
                if(pmax > 0):
                    dB = 10 * np.log10(np.clip(p, pmax/1e8, None)) - 110
                    if(waterfall is None):
                        waterfall = axs.imshow(dB, cmap = 'inferno', vmax = 0, vmin = -40, origin = 'lower')
                    else:
                        waterfall.set_data(dB)
                    plt.pause(0.1)
            if(do_analysis):
                global wsjtx_dicts
                wsjtx_dicts = wsjtx_dicts[-200:]
                do_analysis = False
                analyse_dictionaries(fig_s, ax_s)
                
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False

    time.sleep(1)

    #calibrate_snr()
    show_matched_cands()

show_waterfall = False
show_success_plot = True
    
compare("data/210703_133430", [100,3100])
#compare(None, [100,3100])

#fig_s, ax_s = plt.subplots( figsize=(10,6))
#plot_success(fig_s, ax_s, 'compare_data.pkl')
#plt.show()



