import pickle
import numpy as np
import time
import matplotlib.pyplot as plt
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.candidate import params
from PyFT8.sigspecs import FT8
from PyFT8.tests_wsjtx_all_tailer import Wsjtx_all_tailer
from PyFT8.tests_plot_success import plot_success
from PyFT8.time_utils import tlog, cyclestart_str

global all_decodes
all_decodes = []

def analyse_dictionaries(pyft8_dicts, wsjtx_dicts, cyclestart_str):
    global all_decodes

    wsjtx_dicts = [d for d in wsjtx_dicts if d['cs'] == cyclestart_str]
    pyft8_dicts = [d for d in pyft8_dicts if d['cs'] == cyclestart_str]
    tlog(f"[Analyse dicts] {len(pyft8_dicts)} received from cycle manager matching cycle {cyclestart_str}")

    wsjtx_dicts_cofreqs = [w['f'] for w in wsjtx_dicts for w2 in wsjtx_dicts if 0 <= np.abs(w['f'] - w2['f']) <= 51 and ''.join(w['msg']) != ''.join(w2['msg'])]

    tlog(f"[Analyse dicts] {'Cycle start':<13} {'fHzW':<4} {'cofreq':<6} {'fHzP':<4} {'snrW':<3} {'snrP':<3}  {'dtW':<4} {'dtP':<4} {'tdW':<4} {'tdP':<4}"
              +f"{'msgW':<23} {'msgP':<23} {'sync'} {'llrSD':<4}{'decode_path'}")
    no_match = {'cs':'000000_000000', 'f':0, 'snr':-30, 'dt':0, 'td':'', 'msg':'', 'sync_idx':'', 'llr_sd':0, 'decode_path':'No Match'}

    wsjtx_keys = set()
    pyft8_keys = set()
    for w in wsjtx_dicts:
        w.update({'cofreq': w['f'] in wsjtx_dicts_cofreqs})
        decodes = [p for p in pyft8_dicts if (np.abs(w['f'] - p['f']) < 5 or w['msg'] == p['msg']) and np.abs(float(w['td'])-float(p['td'])) < 10]
        decodes.sort(key = lambda p: (-len(p['msg_tuple']), -p['llr_sd']))
        p = decodes[0] if(len(decodes)) else no_match
        all_decodes.append((w, p))
        pkey = p['cs'] + " " + p['msg']
        pyft8_keys.add(pkey)
        row = f"{w['cs']} {w['f']:4d} {'cofreq' if w['cofreq'] else '  --  '} {p['f']:4d} {w['snr']:+04d} {p['snr']:+04d} {w['dt']:4.1f} {p['dt']:4.1f} "
        row = row + f"{w['td']:<4} {p['td']:<4} {w['msg']:<23} {p['msg']:<23} {p['sync_idx']:>4} {p['llr_sd']:04.2f} {p['decode_path']}" 
        tlog(f"[Analyse dicts] {row}")
        wkey = w['cs'] + " " + w['msg']
        wsjtx_keys.add(wkey)
        
    for p in pyft8_dicts:
        pkey = p['cs'] + " " + p['msg']
        if(p['msg'] != '' and pkey not in pyft8_keys and pkey not in wsjtx_keys):
            all_decodes.append((no_match, p))
            row = f"{p['cs']} {0:4d} {'  --  '} {p['f']:4d} {-30:+04d} {p['snr']:+04d} {0:4.1f} {p['dt']:4.1f} {0:<4} {p['td']:<4} {'':<23} {p['msg']:<23} "
            row = row + f"{p['sync_idx']:>4} {p['llr_sd']:04.2f} {p['decode_path']}"
            tlog(f"[Analyse dicts] {row}")    
        pyft8_keys.add(pkey)
        
    with open("results/data/compare_data.pkl","wb") as f:
        pickle.dump({'decodes':all_decodes, 'params':params}, f)



def run(freq_range):
    
    pyft8_dicts = []
    wsjtx_dicts = []
    cycle_analysed = True

    def on_finished(dicts):
        pyft8_dicts.extend(dicts)

    cycle_manager = Cycle_manager(FT8, on_decode = None, on_finished = on_finished, freq_range = freq_range, 
                                  input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
    wsjtx_all_tailer = Wsjtx_all_tailer(on_decode = lambda d: wsjtx_dicts.append(d), running = True)
    
    if(show_success_plot):
        plt.ion()
        fig_s, ax_s = plt.subplots( figsize=(10,6))
    if(show_waterfall):
        plt.ion()
        fig, axs = plt.subplots(figsize = (20,7))
        plt.tight_layout()
        waterfall = None

    ct_prev = 0
    first_py = False
    first_ws = False
    try:
        while True:
            time.sleep(0.5)
            ct = (time.time()) % 15
            rollover = (ct < ct_prev)
            ct_prev = ct

            if(rollover):
                cycle_to_list = cyclestart_str(time.time() - 30)
                tlog(f"[Test loop] looking at cycle {cycle_to_list}")
                if(not (first_py and first_ws)):
                    if(cycle_to_list in [d['cs'] for d in pyft8_dicts]): first_py = True
                    if(cycle_to_list in [d['cs'] for d in wsjtx_dicts]): first_ws = True
                    if(not first_py): tlog(f"[Test loop] waiting for PyFT8")
                    if(not first_ws): tlog(f"[Test loop] waiting for WSJTX")
                else:
                    analyse_dictionaries(pyft8_dicts, wsjtx_dicts, cycle_to_list)
                    if(show_success_plot):
                        plot_success(fig_s, ax_s, "results/data/compare_data.pkl")
                        plt.pause(0.01)

                if(show_waterfall):
                    p = cycle_manager.spectrum.audio_in.pgrid_main
                    pmax = np.max(p)
                    if(pmax > 0):
                        dB = 10 * np.log10(np.clip(p, pmax/1e8, None)) - 110
                        if(waterfall is None):
                            waterfall = axs.imshow(dB, cmap = 'inferno', vmax = 0, vmin = -40, origin = 'lower')
                        else:
                            waterfall.set_data(dB)
                        plt.pause(0.01)

    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False

show_waterfall = False
show_success_plot = True


run([100,3100])

#fig_s, ax_s = plt.subplots( figsize=(10,6))
#plot_success(fig_s, ax_s, 'compare_data.pkl')
#plt.show()





