
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

dataset = "210703_133430"
freq_range = [100,3000]

def get_wsjtx_decodes():
    with open(dataset + '.txt','r') as f:
        lines = f.readlines()
    wsjtx_dicts = []
    for l in lines:
        wsjtx_dicts.append({'f':int(l[16:21]), 'msg':l[24:].strip(), 'snr':int(l[8:11]), 'dt':float(l[12:16])})
    return wsjtx_dicts

def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

def onCandidateRollover(candidates):

    pyft8_cands = candidates.copy()
    wsjtx_dicts = get_wsjtx_decodes()

    matches = [(w, c) for w in wsjtx_dicts for c in pyft8_cands if abs(w['f'] - c.fHz) < 3]

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
    with open('wav_compare_stats.csv', 'a') as f:
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

def onDecode(c):
    print(c.fHz, c.msg)

def run_PyFT8():
    cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                                  audio_in_wav = dataset + '.wav', verbose = True)
    try:
        while cycle_manager.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping")
        cycle_manager.running = False
   
initialise_outputs()
get_wsjtx_decodes()
run_PyFT8()




    



