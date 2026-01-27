import matplotlib.pyplot as plt
import pandas as pd
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

global wsjtx_dicts, pyft8_cands, new_matches, cands_matched, do_analysis
wsjtx_dicts = []
pyft8_cands = []
new_matches = None
cands_matched = []
historic_matches = []
do_analysis = False

def plot_success(fig, ax):
    
    py      = [[],              [],             [],         [],         [],                 [],         [],         []          ]
    pycols  = ['black',         'lime',         'yellow',   'orange',   'teal',             'green',    'white',    'red'       ]
    pylabs  = ['Hard t+8 sec',  'Immediate',    'OSD2',     'OSD1',     'LDPC &Bitflip',    'LDPC',     'Timeouts', 'Incorrect' ]
    substrs = ['H00',           'I00',          'P00'       'O00',      'A',                'L']

  #  bins = [350 + 5*b for b in range(50)]
    bins = [-30 + 1*b for b in range(60)]
    
    ws = [[],[]]
    pydecs = 0
    pydecs_correct = 0
    pydecs_subs = 0
    for w, c in historic_matches:
        Hz, cofreq, wsnr, q, nc, flags, dpath =c.fHz, w['cofreq'], w['snr'], c.llr0_quality, c.ncheck0, c.flags, c.decode_path
        q = int(wsnr)
        if(not "#" in dpath): py[6].append(q)
        if("C00#" in dpath):
            pydecs +=1
            for i, s in enumerate(substrs):
                if(s in dpath):
                    py[i].append(q)
                    break
            if(not "i" in flags):
                pydecs_correct +=1
            if('r' in flags):
                pydecs_subs += 1
            if("i" in flags):
                py[7].append(q)
      
        if(cofreq):
            ws[1].append(q)
        else:
            ws[0].append(q)

    if(pydecs ==0):
        return

    ax.cla()

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

    ax.set_xlabel("Signal quality = wsjt-x reported snr")
    ax.set_ylabel(f"Number of decodes")

    ntot = len(historic_matches)
    py_pc = f"{int(100*pydecs/ntot)}"
    pyh_pc = f"{int(100*len(py[0])/ntot)}"
    pyc_pc = f"{int(100*pydecs_correct/ntot)}"
    pys_pc = f"{int(100*pydecs_subs/ntot)}"
    fig.suptitle(f"PyFT8 vs WSJTX. {ntot} decodes, {py_pc}% ({pyc_pc}% correct) to PyFT8 ({pyh_pc}% using hard decode only, {pys_pc}% after subtraction )")

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
            wsjtx_dicts.append({'cs':cs,'f':int(freq),'msg':msg, 't':time.time(),'dt':dt,'snr':snr,'td': f"{time.time() %60:5.2f}"})
        except:
            print(f"Wsjtx_tailer error in line '{line}'")

def get_wsjtx_decodes(decodes_file):
    global wsjtx_dicts
    with open(decodes_file,'r') as f:
        lines = f.readlines()
    for l in lines:
        wsjtx_dicts.append({'cs':'any', 'f':int(l[16:21]), 'msg':l[24:].strip(), 'snr':int(l[8:11]), 'dt':float(l[12:16]), 'td':''})

def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

def onCandidateRollover(candidates):
    global pyft8_cands, do_analysis
    pyft8_cands = candidates.copy()
    do_analysis = True

def analyse_dictionaries(fig_s, ax_s):
    global cands_matched, new_matches
    time.sleep(2)

    new_matches = [(w, c) for w in wsjtx_dicts for c in pyft8_cands if abs(w['f'] - c.fHz) < 3
               and (w['cs'] == c.cyclestart_str or w['cs']=='any')]
    
    best = {}
    for w, c in new_matches:
        key = (w['cs'], w['msg'])
        has_message = True if c.msg else False
        score = (has_message, c.llr0_quality)
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
    with open('data/compare_wsjtx.csv', 'a') as f:
        for w, c in new_matches:
            cands_matched.append(c)
            td = f"{c.decode_completed %60:5.2f}" if c.decode_completed else '     '
            w.update({'cofreq': w['f'] in wsjtx_cofreqs})
            msg = ' '.join(c.msg) if c.msg else ''
            c.incorrect = (msg !='' and msg != w['msg'])
            c.flags = f"{'-' if c.subtracted else ' '}{'r' if c.reprocessed else ' '}{'i' if c.incorrect else ' '}"
            cofreq = 'cofreq' if w['cofreq'] else "  --  "
            basics = f"{w['cs']} {w['f']:4d} {cofreq} {c.fHz:4d} {w['snr']:+03d} {c.snr:+03d} {w['dt']:4.1f} {c.tsecs:4.1f} {w['td']} {td}"
            if(msg !=''): unique.add(msg)
            print(f"{basics} {w['msg']:<23} {msg:<23} {c.llr0_quality:3.0f} {c.flags} {c.decode_path}")
            historic_matches.append((w,c))

    print(f"{len(unique)} unique decodes")
    if(not len(unique)):
        print("Is WSJT-X running??")
    unprocessed = [c for w, c in new_matches if not "#" in c.decode_path]
    if(len(unprocessed)):
        best_unprocessed_quality = np.max([c.llr0_quality for c in unprocessed])
        best_unprocessed_ncheck0 = np.min([c.ncheck0 for c in unprocessed])
        print(f"{len(unprocessed)} unprocessed candidates decoded by wsjt-x, best qual {best_unprocessed_quality:4.0f} best ncheck0 {best_unprocessed_ncheck0}")
    if(show_success_plot):
        plot_success(fig_s, ax_s)
        plt.pause(0.1)
    
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
            axs[i].set_ylabel(f"{c.msg} {'SUB' if c.subtracted else ''} {'REP' if c.reprocessed else ''}", fontsize=8)
    plt.tick_params(labelleft=False)
    plt.tight_layout()
    plt.show()

            
def compare(dataset, freq_range, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"):
    global do_analysis

    if(dataset):
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, test_speed_factor = 1, max_cycles = 2, 
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                                      audio_in_wav = dataset+".wav", verbose = True, subtraction = do_subtraction)
        get_wsjtx_decodes(dataset+".txt")
    else:
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None,
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                                      input_device_keywords = ['Microphone', 'CODEC'], verbose = True, subtraction = do_subtraction)
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

do_subtraction = False
show_waterfall = False
show_success_plot = True
    
compare("data/210703_133430", [100,3100])

#compare(None, [100,3100])

    



