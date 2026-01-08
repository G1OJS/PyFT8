
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"
wsjtx_dicts = []
pyft8_cands = []
cyclestarts = []
freq_range = [200,3100]

running = True

def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

def wsjtx_all_tailer(all_txt_path):
    def follow():
        with open(all_txt_path, "r") as f:
            f.seek(0, 2)
            while running:
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
            global wsjtx_dicts
            wsjtx_dicts.append({'cs':cs,'f':int(freq),'msg':msg, 't':time.time(),'dt':dt,'snr':snr,'info':''})
        except:
            pass

def onCandidateRollover(candidates):
    global wsjtx_dicts, pyft8_cands, cyclestarts
    if(not len(candidates)>2 ):
        return
    cycle = candidates[-1].cyclestart_str
    cyclestarts.append(cycle)
    pyft8_cands = pyft8_cands + candidates.copy()

    if(len(cyclestarts) > 0):
        display_cycle = cyclestarts[-1]
        threading.Thread(target = display, args=(display_cycle,)).start()
    
def display(cycle):
       
    _wsjtx_dicts = [w for w in wsjtx_dicts if w['cs'] == cycle and w['f'] >= freq_range[0] and w['f'] <= freq_range[1] ]
    _pyft8_cands = [c for c in pyft8_cands if c.cyclestart_str == cycle]
    
    matches = [(w, c) for w in _wsjtx_dicts for c in _pyft8_cands if abs(w['f'] - c.fHz) < 2]
    if(len(matches) == 0):
        return

    best = {}
    for w, c in matches:
        key = (w['cs'], w['msg'])
        decoded = True if c.msg else False
        score = (decoded, -c.snr, abs(w['f'] - c.fHz))
        if key not in best or score > best[key][0]:
            best[key] = (score, w, c)
    matches = [(w, c) for (_, w, c) in best.values()]

    successes = [c for w, c in matches if "SENTENCER: CRC_passed" in c.decode_history[-1]['step']]
    succeded = len(successes)
    succeded_imm = len([c for c in successes if "I:00" in c.decode_history[0]['step']])
    succeded_bf_ldpc =len([c for c in successes if any(["B" in h['step'] for h in c.decode_history])])
    succeded_ldpc = succeded - succeded_bf_ldpc - succeded_imm

    failures = [c for w, c in matches if not "SENTENCER: CRC_passed" in c.decode_history[-1]['step']]
    failed_init = len([c for c in failures if "SENTENCER: NCI" in c.decode_history[-1]['step']])
    failed_ldpc = len([c for c in failures if "SENTENCER: STALL" in c.decode_history[-1]['step'] and any(["B" in h['step'] for h in c.decode_history])])
    failed_bf_ldpc = len([c for c in failures if "SENTENCER: STALL" in c.decode_history[-1]['step'] and not any(["B" in h['step'] for h in c.decode_history])])
    failed_timeout = len([c for c in failures if not "SENTENCER" in c.decode_history[-1]['step']])

    print()
    print("Si,Sl,Sb,Fi,Fl,Fb,Ft,%")
    total = len(matches)
    op = f"{succeded_imm:2d},{succeded_ldpc:2d},{succeded_bf_ldpc:2d},{failed_init:2d},{failed_ldpc:2d},{failed_bf_ldpc:2d},{failed_timeout:2d},{pc_str(succeded, total)}"
    print(op)
    with open('live_compare_stats.csv', 'a') as f:
        f.write(f"{op}\n")

    with open('wav_compare.csv', 'a') as f:
        for w, c in matches:
            basics = f"{c.cyclestart_str} {w['f']:4d} {c.fHz:4d} {w['snr']:+03d} {c.snr:+03d} {w['dt']:4.1f} {c.dt:4.1f}"
            msg = ' '.join(c.msg) if c.msg else ''
            steps = ','.join([h['step'] for h in c.decode_history])
            conf = ','.join([f"{v:3.2f}" for v in c.conf_percentiles])
            op = f"{basics} {w['msg']:<25} {msg:<25} {conf:<20} {steps}"
            f.write(f"{op}\n")
            print(op)

    with open('decodes.csv', 'a') as f:
        for w, c in matches:
            f.write(f"{c.decode_history[0]['nc']},{'True' if c.msg else 'False'}\n")

def initialise_outputs():
    with open('decodes','w') as f:
        f.write('')
    with open('wav_compare.csv', 'w') as f:
        f.write('')
    with open('wav_compare_stats.csv', 'w') as f:
        f.write("succeded_imm,succeded_ldpc,succeded_bf_ldpc,failed_init,failed_ldpc,failed_bf_ldpc,failed_timeout,percent\n")

def run_PyFT8():
    cycle_manager = Cycle_manager(FT8, None, onOccupancy = None, onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                              input_device_keywords = ['Microphone', 'CODEC'], verbose = False)
    try:
        while cycle_manager.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False

def run_wsjtx_tailer():
    threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path,)).start()   

initialise_outputs()
run_wsjtx_tailer()
run_PyFT8()



    



