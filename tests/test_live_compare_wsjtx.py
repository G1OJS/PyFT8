
import threading
import numpy as np
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"

wsjtx = []
pyft8 = []
cycles = []
cycle_info = {}
    
running = True
def onCandidateRollover(candidates):
    global pyft8
    if(not len(candidates)>2 ):
        return
    cycle = candidates[-1].cyclestart_str
    for c in candidates:
        msg = ' '.join(c.msg) if c.msg else ''
        pyft8.append({'cs':c.cyclestart_str, 'f':int(c.fHz),'msg':msg, 't':time.time(), 'dt':0, 'snr':c.snr, 'info':c.info})

    nsynced   = len([c.sync_completed for c in candidates if not c.deduplicated == "sync"])
    ndemapped = len([c.demap_completed for c in candidates if c.demap_completed])
    ndecoded  = len([c.decode_completed for c in candidates if c.decode_completed])
    t_sync = np.max([c.sync_completed for c in candidates if c.sync_completed]) - np.min([c.sync_started for c in candidates if c.sync_started])
    t_demap = np.sum([c.demap_completed - c.demap_started for c in candidates if c.demap_completed])
    t_decode = np.sum([c.decode_completed - c.decode_started for c in candidates if c.decode_completed])
    
    t_sync, t_demap, t_decode = float(f"{t_sync:5.2f}"), float(f"{t_demap:5.2f}"), float(f"{t_decode:5.2f}"), 
    cycle_info[cycle] = {'synced':nsynced, 'demapped':ndemapped, 'decoded':ndecoded, 't_sync':t_sync, 't_demap':t_demap, 't_decode':t_decode}
    
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
            global wsjtx
            wsjtx.append({'cs':cs,'f':int(freq),'msg':msg, 't':time.time(),'dt':dt,'snr':snr,'info':''})
        except:
            pass

def pc_str(x,y):
    return "{}" if y == 0 else f"{int(100*x/y)}%"

threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path,)).start()   
cycle_manager = Cycle_manager(FT8, None, onOccupancy = None, onCandidateRollover = onCandidateRollover,
                              input_device_keywords = ['Microphone', 'CODEC'], verbose = False)

def analyse():
    global wsjtx, pyft8, cycles
    if(len(wsjtx)>1 and len(pyft8)>1):
        cycle = wsjtx[-1]['cs']
        cycles.append(cycle)
        cycles = cycles[-5:]
        if(len(cycles)<2):
            return

        display_cycle = cycles[-2]
        
        _wsjtx = [w for w in wsjtx if w['cs'] == display_cycle]
        _pyft8 = [p for p in pyft8 if p['cs'] == display_cycle]
        
        matches = [(w, p) for w in _wsjtx for p in _pyft8 if w['cs'] == p['cs'] and abs(w['f'] - p['f']) < 2]
        if(len(matches) == 0):
            return

        best = {}
        for w, p in matches:
            key = (w['cs'], w['msg'])
            decoded = p.get('msg', False)
            df = abs(w['f'] - p['f'])
            snr = p.get('snr', -999)
            score = (decoded, -snr, df)
            if key not in best or score > best[key][0]:
                best[key] = (score, w, p)
        matches = [(w, p) for (_, w, p) in best.values()]

        succeded_imm = len([1 for w, p in matches if "Decoded-D " in p['info']])
        succeded_ldpc = len([1 for w, p in matches if "Decoded-DL " in p['info']])
        succeded_bf_ldpc = len([1 for w, p in matches if "Decoded-DBL " in p['info']])
        succeded = succeded_imm + succeded_ldpc + succeded_bf_ldpc
        failed_bf_ldpc = len([1 for w, p in matches if "Failed-DBL " in p['info']])
        failed  = len([1 for w, p in matches if "Failed" in p['info']])
        starved  = len([1 for w, p in matches if not "Decoded" in p['info'] and not "Failed" in p['info']])
        total = succeded + failed + starved

        ci = cycle_info[display_cycle]
        print()
        print("Cycle,Synced,Demapped,Decoded,t_sync,t_demap,t_decode,Sinst,Sldpc,Sflip,Failed,Undecoded,percent")
        print(cycle, ci['synced'], ci['demapped'], ci['decoded'], ci['t_sync'], ci['t_demap'], ci['t_decode'], succeded_imm, succeded_ldpc, succeded_bf_ldpc, failed, starved, pc_str(succeded, total))
        with open('live_compare_stats.csv', 'a') as f:
            f.write(f"{cycle},{ci['synced']},{ci['demapped']},{ci['decoded']},{ci['t_sync']},{ci['t_demap']},{ci['t_decode']},{succeded_imm},{succeded_ldpc},{succeded_bf_ldpc},{failed},{starved},{pc_str(succeded, total)}\n")

        with open('live_compare.csv', 'a') as f:
            for w, p in matches[-50:]:
                f.write(f"{w['cs']} {w['msg']:<25} {p['msg']:<25} {p['info']}\n")

with open('live_compare.csv', 'w') as f:
    f.write('')
            
with open('live_compare_stats.csv', 'w') as f:
    f.write("Cycle,Synced,Demapped,Decoded,t_sync,t_demap,t_decode,Sinst,Sldpc,Sflip,Failed,Undecoded,percent\n")
stats_flag = False
try:
    while True:
        time.sleep(0.5)
        if time.time() % 15 < 5:
            stats_flag = False
        if time.time() % 15 > 10 and not stats_flag:
            stats_flag = True
            analyse()

except KeyboardInterrupt:
    print("\nStopping PyFT8 Rx")
    cycle_manager.running = False
    running = False


    



