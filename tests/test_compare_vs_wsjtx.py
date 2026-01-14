
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
import matplotlib.pyplot as plt

global wsjtx_dicts, pyft8_cands
wsjtx_dicts = []
pyft8_cands = []

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
    
    global pyft8_cands
    pyft8_cands = candidates.copy()
    threading.Thread(target = analyse_dictionaries).start()

def analyse_dictionaries():
    time.sleep(2)

    matches = [(w, c) for w in wsjtx_dicts for c in pyft8_cands if c.demap_completed
               and abs(w['f'] - c.fHz) < 3 and (w['cs'] == c.cyclestart_str or w['cs']=='any')]
    
    best = {}
    for w, c in matches:
        key = (w['cs'], w['msg'])
        has_message = True if c.msg else False
        score = (has_message, -abs(w['f'] - c.fHz))
        if key not in best or score > best[key][0]:
            best[key] = (score, w, c)
    matches = [(w, c) for (_, w, c) in best.values()]

    wsjtx_cofreqs = [w['f'] for w,c in matches for w2,c in matches if 0 <= np.abs(w['f'] - w2['f']) <= 2 and ''.join(w['msg']) != ''.join(w2['msg'])]

    pyft8 = [c for c in pyft8_cands if c.msg]
    pyft8_msgs = [c.msg for c in pyft8]
    pyft8 = [c for c in pyft8 if c.msg not in pyft8_msgs]
    wsjtx_msgs = [w['msg'] for w in wsjtx_dicts]
    pyft8_only = [c for c in pyft8 if ' '.join(c.msg) not in wsjtx_msgs]
    
    unique = set()
    with open('compare_wsjtx.csv', 'a') as f:
        for w, c in matches:
            td = f"{c.decode_completed %60:5.2f}" if c.decode_completed else '     '
            cofreq = "cofreq" if w['f'] in wsjtx_cofreqs else "  --  "
            basics = f"{c.cyclestart_str} {w['f']:4d} {cofreq} {c.fHz:4d} {w['snr']:+03d} {c.snr:+03d} {w['dt']:4.1f} {c.dt:4.1f} {w['td']} {td}"
            msg = ' '.join(c.msg) if c.msg else ''
            if(msg !=''): unique.add(msg)
            op = f"{basics} {w['msg']:<23} {msg:<23} {c.llr0_quality:4.0f} {c.decode_path}"
            f.write(f"{op}\n")
            print(op)

    print(f"{len(unique)} unique decodes")    

def initialise_outputs():
    with open('compare_wsjtx.csv', 'w') as f:
        f.write('')

def onDecode(c):
    pass

def update_charts():
    global fig, ax
    
    if any(pyft8_cands):
        demapper_output = [c.llr0_quality for c in pyft8_cands]
        ax.hist(demapper_output, label = "Initial",
            cumulative = 0, color = '#388E3C', alpha = 0.8, lw=0.5, edgecolor = "black")
        plt.pause(0.1)

            

def compare(dataset, freq_range, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"):
    global fig, ax
   # fig, ax = plt.subplots()
   # plt.ion()
   # plt.pause(0.5)

    initialise_outputs()
    
    if(dataset):
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, test_speed_factor = 1, 
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                                      audio_in_wav = dataset+".wav", verbose = True)
        get_wsjtx_decodes(dataset+".txt")
    else:
        cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None,
                                      onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                                      input_device_keywords = ['Microphone', 'CODEC'], verbose = True)
        threading.Thread(target=wsjtx_all_tailer, args = (all_file,cycle_manager,)).start()
        
    try:
        while cycle_manager.running:
           # update_charts()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False

#compare("210703_133430", [100,3100])

compare(None, [100,3100])


    



