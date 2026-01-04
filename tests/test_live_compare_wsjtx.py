
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

    if(len(cyclestarts) > 1):
        display_cycle = cyclestarts[-2]
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

    total = len(matches)

    nsynced   = len(_pyft8_cands)
    ndemapped = len([c for c in _pyft8_cands if c.demap_completed])
    ndecoded  = len([c for c in _pyft8_cands if c.decode_completed])
    t_sync = np.max([c.sync_completed for c in _pyft8_cands if c.sync_completed]) - np.min([c.sync_started for c in _pyft8_cands if c.sync_started])
    t_demap = np.sum([c.demap_completed - c.demap_started for c in _pyft8_cands if c.demap_completed])
    t_decode_successes = np.sum([c.decode_completed - c.decode_started for c in _pyft8_cands if c.decode_completed and c.msg])
    t_decode_failures = np.sum([c.decode_completed - c.decode_started for c in _pyft8_cands if c.decode_completed and not c.msg])
    
    succeeded = [c for w, c in matches if c.msg]
    succeded = len(succeeded)
    succeded_imm = len([1 for c in succeeded if "I00" in c.info])
    succeded_ldpc = len([1 for c in succeeded if "L00" in c.info])
    succeded_bf_ldpc = len([1 for c in succeeded if "B" in c.info and "00" in c.info])


    failed  = len([1 for w, c in matches if c.decode_completed and not c.msg])
    starved  = len([1 for w, c in matches if not c.decode_completed and not c.msg])

    UNCs  = [c.ncheck_initial for w, c in matches if not c.msg]
    MUNC = np.min(UNCs)

    print()
    print("Cycle,Synced,Demapped,Decoded,MUNC,t_sync,t_demap,t_decode_s,t_decode_f,Sinst,Sldpc,Sflip,Failed,Undecoded,percent")
    print(cycle, "Counts: ",nsynced,ndemapped,ndecoded,MUNC, "Times: ", f"{t_sync:5.2f}",f"{t_demap:5.2f}",f"{t_decode_successes:5.2f}",f"{t_decode_failures:5.2f}",
          "Success: ", succeded_imm, succeded_ldpc, succeded_bf_ldpc, "Failed:", failed, starved, pc_str(succeded, total))
    with open('live_compare_stats.csv', 'a') as f:
        f.write(f"{cycle},{nsynced},{ndemapped},{ndecoded},{MUNC},{t_sync},{t_demap},"
                +f"{t_decode_successes},{t_decode_failures},{succeded_imm},{succeded_ldpc},{succeded_bf_ldpc},{failed},{starved},{pc_str(succeded, total)}\n")

    with open('live_compare.csv', 'a') as f:
        for w, c in matches[-50:]:
            msg = ' '.join(c.msg) if c.msg else ''
            f.write(f"{w['cs']} {w['msg']:<25} {msg:<25} {c.info}\n")



with open('live_compare.csv', 'w') as f:
    f.write('')
            
with open('live_compare_stats.csv', 'w') as f:
    f.write("Cycle,Synced,Demapped,Decoded,MUNC,t_sync,t_demap,t_decode_s,t_decode_f,Sinst,Sldpc,Sflip,Failed,Undecoded,percent\n")

threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path,)).start()   
cycle_manager = Cycle_manager(FT8, None, onOccupancy = None, onCandidateRollover = onCandidateRollover, freq_range = freq_range,
                              input_device_keywords = ['Microphone', 'CODEC'], verbose = False)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping")
    cycle_manager.running = False
    running = False


    



