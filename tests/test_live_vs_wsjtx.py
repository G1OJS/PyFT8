import pickle
import numpy as np
import time
import matplotlib.pyplot as plt
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.candidate import params
from PyFT8.sigspecs import FT8
from PyFT8.tests_wsjtx_all_tailer import Wsjtx_all_tailer
from PyFT8.tests_plot_success import plot_success
  
def analyse_dictionaries(fig_s, ax_s, pyft8_dicts, wsjtx_dicts):

    if(not len(wsjtx_dicts)):
        print("No WSJT-X decodes - is WSJT-X running?")
        return

    this_cycle_start = wsjtx_dicts[-1]['cs']
    wsjtx_dicts_cycle = [w for w in wsjtx_dicts if (int(w['cycle_idx']) == test_cycle_counter)
                        or (w['cycle_idx'] == -1)]
    wsjtx_dicts_cofreqs = [w['f'] for w in wsjtx_dicts for w2 in wsjtx_dicts if 0 <= np.abs(w['f'] - w2['f']) <= 51 and ''.join(w['msg']) != ''.join(w2['msg'])]

    new_matches = [(w, p) for w in wsjtx_dicts_cycle for p in pyft8_dicts if abs(w['f'] - p['f']) < 4]
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
        w.update({'cofreq': w['f'] in wsjtx_dicts_cofreqs})
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
        plot_success(fig_s, ax_s)
        time.sleep(0.001)
        plt.pause(0.5)
        time.sleep(0.001)

    with open("results/data/compare_data.pkl","wb") as f:
        pickle.dump({'matches':historic_matches, 'params':params}, f)

def run(freq_range):
    pyft8_dicts = []
    wsjtx_dicts = []
    cycle_analysed = False

    cycle_manager = Cycle_manager(FT8, on_decode = lambda d: pyft8_dicts.append(d), freq_range = freq_range, 
                                  input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
    wsjtx_all_tailer = Wsjtx_all_tailer(on_decode = lambda d: wsjtx_dicts.append(d), running = cycle_manager.running)
    
    if(show_success_plot):
        plt.ion()
        fig_s, ax_s = plt.subplots( figsize=(10,6))
        plot_success(fig_s, ax_s, "results/data/compare_data.pkl")
    if(show_waterfall):
        plt.ion()
        fig, axs = plt.subplots(figsize = (20,7))
        plt.tight_layout()
        waterfall = None
    try:
        while True:
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
            if(time.time() % 15 > 5 and not cycle_analysed):
                analyse_dictionaries(fig_s, ax_s, pyft8_dicts, wsjtx_dicts)
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





