import pickle
import numpy as np
import time
import matplotlib.pyplot as plt
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.candidate import params
from PyFT8.sigspecs import FT8
from PyFT8.tests_wsjtx_all_tailer import Wsjtx_all_tailer
from PyFT8.tests_plot_success import plot_success
from PyFT8.time_utils import tlog

global all_decodes
all_decodes = []

def analyse_dictionaries(pyft8_dicts, wsjtx_dicts):
    global all_decodes
    if(not len(wsjtx_dicts)):
        print("No WSJT-X decodes - is WSJT-X running?")
        return

    wsjtx_dicts_cofreqs = [w['f'] for w in wsjtx_dicts for w2 in wsjtx_dicts if 0 <= np.abs(w['f'] - w2['f']) <= 51 and ''.join(w['msg']) != ''.join(w2['msg'])]

    print(f"{'Cycle start':<13} {'fHzW':<4} {'cofreq':<6} {'fHzP':<4} {'snrW':<3} {'snrP':<3} {'dtW':<4} {'dtP':<4} {'tdW':<4} {'tdP':<4}"
              +f"{'msgW':<23} {'msgP':<23} {'llrSD':<4} {'decode_path'}")
    no_match = {'Cycle start':'000000_000000', 'f':0, 'snr':-30, 'dt':0, 'td':'', 'msg':'', 'llr0_sd':0, 'decode_path':'No Match'}

    wsjtx_msgs = []
    for w in wsjtx_dicts:
        w.update({'cofreq': w['f'] in wsjtx_dicts_cofreqs})
        decodes = [p for p in pyft8_dicts if np.abs(w['f'] - p['f']) < 4]
        decodes.sort(key = lambda p: (p['msg'], p['llr0_sd']))
        p = decodes[0] if(len(decodes)) else no_match
        all_decodes.append((w, p))
        row = f"{w['cs']} {w['f']:4d} {'cofreq' if w['cofreq'] else '  --  '} {p['f']:4d} {w['snr']:+04d} {p['snr']:+04d} {w['dt']:4.1f} {p['dt']:4.1f} {w['td']:<4} {p['td']:<4} {w['msg']:<23} {p['msg']:<23} {p['llr0_sd']:04.2f} {p['decode_path']}" 
        print(row)
        wsjtx_msgs.append(w['msg'])
        
    pyft8_unique = set ()
    for p in pyft8_dicts:
        if(p['msg'] != '' and p['msg'] not in pyft8_unique and p['msg'] not in wsjtx_msgs):
            all_decodes.append((no_match, p))
            if(p['msg'].replace(" ","") not in wsjtx_msgs):
                row = f"{p['cs']} {0:4d} {'  --  '} {p['f']:4d} {-30:+04d} {p['snr']:+04d} {0:4.1f} {p['dt']:4.1f} {0:<4} {p['td']:<4} {'':<23} {p['msg']:<23} {p['llr0_sd']:04.2f} {p['decode_path']}"
                print(row)
        pyft8_unique.add(p['msg'])
                
    tlog(f"[Analyse dictionaries] Unique decodes pyft8: {len(pyft8_unique)} wsjt-x: {len(wsjtx_dicts)} ")

    with open("results/data/compare_data.pkl","wb") as f:
        pickle.dump({'decodes':all_decodes, 'params':params}, f)

def run(freq_range):
    pyft8_dicts = []
    wsjtx_dicts = []
    cycle_analysed = True

    cycle_manager = Cycle_manager(FT8, on_decode = lambda d: pyft8_dicts.append(d), on_decode_include_failures = True, freq_range = freq_range, 
                                  input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
    wsjtx_all_tailer = False
    
    if(show_success_plot):
        plt.ion()
        fig_s, ax_s = plt.subplots( figsize=(10,6))
    if(show_waterfall):
        plt.ion()
        fig, axs = plt.subplots(figsize = (20,7))
        plt.tight_layout()
        waterfall = None
    try:
        while True:
            time.sleep(1)
            if(time.time() % 15 < 1 and cycle_analysed):
                cycle_analysed = False
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
            if(len(pyft8_dicts) and not wsjtx_all_tailer):
                wsjtx_all_tailer = Wsjtx_all_tailer(on_decode = lambda d: wsjtx_dicts.append(d), running = cycle_manager.running)

            if(time.time() % 15 > 10 and not cycle_analysed):
                if(len(pyft8_dicts)):
                    analyse_dictionaries(pyft8_dicts, wsjtx_dicts)
                    if(show_success_plot):
                        plot_success(fig_s, ax_s, "results/data/compare_data.pkl")
                        plt.pause(0.5)
                pyft8_dicts = []
                wsjtx_dicts = []
                cycle_analysed = True
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False

show_waterfall = False
show_success_plot = True


run([100,3100])

#plot_success_file('compare_data.pkl')





