import matplotlib.pyplot as plt
import pandas as pd
import pickle
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager, params
from PyFT8.sigspecs import FT8

global other_decoder_dicts, new_matches, historic_matches, do_analysis, params, test_cycle_counter, pyft8_dicts_cycle
other_decoder_dicts = []
new_matches = None
historic_matches = []
do_analysis = False
test_cycle_counter = 1
waterfall = None

def plot_success(fig, ax, source, other_decoder_suffix, load_file = False):
    global historic_matches, params

    if(load_file):
        with open("results/data/compare_data.pkl", "rb") as f:
            d = pickle.load(f)
        historic_matches = d['matches']
        params = d['params']
        other_decoder_suffix = d['other_decoder_suffix']

    if not any(historic_matches):
        return
    
    py =        [[],[],[],[],[],[]]
    pycols  =   ['lime', 'green', 'yellow', 'red', '#c0e7fa', '#ebf6fa']
    pylabs  =   ['Immediate', 'LDPC', 'OSD', 'ERR', 'Stall', 'Timeout' ]
    ws =        [[],[]]
    wcols =     ['#141700','#664b07']
    wlabs =     ['isolated','overlapping']

    bins = [0.4 + 0.1*b for b in range(25)]
    
    for w, p in historic_matches:
        q = p['llr0_sd']

        if(w['cofreq']):
            ws[1].append(q)
        else:
            ws[0].append(q)

        if(p['msg']):
            if(p['msg'] == w['msg']):
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
            title = other_decoder_suffix, title_fontproperties = {'weight':'bold', 'size':9}, alignment='left')
    ax.add_artist(dict_2_legend)
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
    fig.suptitle(f"{source}\nPyFT8 {pydecs} vs {other_decoder_suffix} {wdecs} decodes, {pytot_pc}% ({pycorr_pc}% correct) to PyFT8")
    if(params):
        params1 = dict(list(params.items())[:len(params)//2])
        params2 = dict(list(params.items())[len(params)//2:])
        plt.text(0,1.05, params1, fontsize = 6, transform = ax.transAxes)
        plt.text(0,1.02, params2, fontsize = 6, transform = ax.transAxes)
    plt.savefig("compare_results.png")

def wsjtx_all_tailer(all_file, cycle_manager):
    global other_decoder_dicts
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
            other_decoder_dicts.append({'cs':cs,'f':int(freq),'msg':msg, 'dt':dt,'snr':snr,'td': f"{time.time() %60:4.1f}", 'cycle_idx':-1})
        except:
            print(f"Wsjtx_tailer error in line '{line}'")

def read_wsjtx_format(wav_decodes_file):
    print(f"Reading {wav_decodes_file}")
    with open(wav_decodes_file,'r') as f:
        lines = f.readlines()
    cycle_idx = 0
    cyclestart_str = ''
    dicts = []
    for l in lines:
        if(l.startswith('-')):
            continue
        fields = l.split()
        if(fields[0] != cyclestart_str):
            cycle_idx +=1
            cyclestart_str = fields[0]
        try:
            tilde_offset = 1 if("~" in fields) else 0
            msg = fields[4 + tilde_offset].strip() + ' ' + fields[5 + tilde_offset].strip() + ' ' + fields[6 + tilde_offset].strip()
            d = {'cs':cyclestart_str, 'cycle_idx':cycle_idx, 'f':int(fields[3]), 'msg':msg, 'snr':int(float(fields[1])), 'dt':float(fields[2]), 'td':''}
            dicts.append(d)
        except:
            print(f"Error reading line {l}")
    return dicts
 
def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

def onCandidateRollover(candidates):
    global do_analysis, pyft8_dicts_cycle
    pyft8_cands = candidates.copy()
    pyft8_dicts_cycle = []
    for c in pyft8_cands:
        td = f"{c.decode_completed %60:4.1f}" if c.decode_completed else '     '
        d = {'cs':c.cyclestart_str, 'cycle_idx':c.cycle_counter, 'f':c.fHz, 'msg':' '.join(c.msg), 'snr':c.snr,
             'dt':c.dt, 'td':td, 'ncheck0':c.ncheck0, 'llr0_sd':c.llr0_sd, 'td':td, 'decode_path':c.decode_path}
        pyft8_dicts_cycle.append(d)
    
    do_analysis = True

def analyse_dictionaries(fig_s, ax_s, source, other_decoder_dicts, other_decoder_suffix):
    global new_matches, test_cycle_counter

    this_cycle_start = other_decoder_dicts[-1]['cs']
    other_decoder_dicts_cycle = [w for w in other_decoder_dicts if (int(w['cycle_idx']) == test_cycle_counter)
                        or (w['cycle_idx'] == -1 and w['cs'] == this_cycle_start)]
    other_decoder_dicts_cofreqs = [w['f'] for w in other_decoder_dicts for w2 in other_decoder_dicts if 0 <= np.abs(w['f'] - w2['f']) <= 51 and ''.join(w['msg']) != ''.join(w2['msg'])]

    new_matches = [(w, p) for w in other_decoder_dicts_cycle for p in pyft8_dicts_cycle if abs(w['f'] - p['f']) < 4]
    test_cycle_counter +=1

    best = {}
    for w, p in new_matches:
        key = (w['cs'], w['msg'])
        has_message = True if p['msg'] else False
        score = (has_message, p['llr0_sd'])
        if key not in best or score > best[key][0]:
            best[key] = (score, w, p)
    new_matches = [(w, p) for (_, w, p) in best.values()]

    new_matches.sort(key = lambda tup: tup[1]['f'])
    unique = set()
    print(f"{'Cycle start':<13} {'fHzW':<4} {'cofreq':<6} {'fHzP':<4} {'snrW':<3} {'snrP':<3} {'dtW':<4} {'dtP':<4} {'tdW':<4} {'tdP':<4}"
              +f"{'msgW':<23} {'msgP':<23} {'llrSD':<4} {'decode_history'}")
    for w, p in new_matches:
        w.update({'cofreq': w['f'] in other_decoder_dicts_cofreqs})
        basics = f"{w['cs']} {w['f']:4d} {'cofreq' if w['cofreq'] else "  --  "}"
        basics = basics + f"{p['f']:4d}{w['snr']:+04d} {p['snr']:+04d} {w['dt']:4.1f} {p['dt']:4.1f} {w['td']:<4} {p['td']:<4}"
        if(p['msg'] !=''): unique.add(p['msg'])
        print(f"{basics} {w['msg']:<23} {p['msg']:<23} {p['llr0_sd']:04.2f} {p['decode_path']}")
        historic_matches.append((w, p))
        with open('latest_test.txt','a') as f:
            YN = "Y" if p['msg'] else "N"
            f.write(f"{w['cs']} {w['snr']:>3} {w['dt']:3.1f} {w['f']:>3} {w['msg']:>3} {YN}\n") 
  #  for p in pyft8_only:
  #      basics = f"{p['cyclestart_str']} {0:4d} {"  --  "} {p['snr']:+04d} {0:4.1f} {p['dt']:4.1f} {'':<4} {p['td']:<4}"

    print(f"{len(unique)} unique decodes")
    unprocessed = [p for w, p in new_matches if not "#" in p['decode_path']]
    if(len(unprocessed)):
        best_unprocessed_quality = np.max([p['llr0_sd'] for p in unprocessed])
        best_unprocessed_ncheck0 = np.min([p['ncheck0'] for p in unprocessed])
        print(f"{len(unprocessed)} unprocessed candidates decoded by other decoder, best qual {best_unprocessed_quality:4.2f} best ncheck0 {best_unprocessed_ncheck0}")
    if(show_success_plot):
        plot_success(fig_s, ax_s, source, other_decoder_suffix)
        time.sleep(0.001)
        plt.pause(0.5)
        time.sleep(0.001)

    with open("results/data/compare_data.pkl","wb") as f:
        pickle.dump({'matches':historic_matches, 'params':params, 'other_decoder_suffix':other_decoder_suffix}, f)

def onDecode(c):
  #  print(c.fHz, c.msg)
    pass

def run(dataset, other_decoder_suffix, freq_range, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"):
    global do_analysis

    if(dataset):
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, test_speed_factor = 1, max_cycles = 2, 
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,  
                                      audio_in_wav = dataset+".wav", verbose = True)
        other_decoder_dicts = read_wsjtx_format(dataset+other_decoder_suffix+".txt")
        source = dataset
    else:
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None,
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range, 
                                      input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
        source = "Live"
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
                do_analysis = False
                analyse_dictionaries(fig_s, ax_s, source,  other_decoder_dicts, other_decoder_suffix)
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False
    time.sleep(1)

def plot_success_file(file):
    fig_s, ax_s = plt.subplots( figsize=(10,6))
    plot_success(fig_s, ax_s, file)
    plt.show()

show_waterfall = False
show_success_plot = True

for n in range(1,2):
    run(r"C:\Users\drala\Documents\Projects\ft8_lib test\test\wav\20m_busy\test_"+f"{n:02d}", "_ft8_lib", [100,3100])

#run(r"C:\Users\drala\Documents\Projects\ft8_lib test\test\wav\20m_busy\test_01", [100,3100])

#run("data/G4WNT/FT-8-Comp-31-12-22-5mins-2-12000", [100,3100])
#run("data/210703_133430", [100,3100])
#run(None, [100,3100])

#plot_success_file('compare_data.pkl')





