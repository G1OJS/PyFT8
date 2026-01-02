
import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"

wsjtx = []
pyft8 = []
    
running = True
def onCandidateRollover(candidates):
    global pyft8
    for c in candidates:
        msg = ' '.join(c.msg) if c.msg else ''
        pyft8.append({'cs':c.cyclestart_str, 'f':int(c.fHz),'msg':msg, 't':time.time(), 'dt':0, 'snr':c.snr, 'info':c.info})
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


try:
    while True:
        time.sleep(1)
        matches = [(w, p) for w in wsjtx for p in pyft8 if w['cs'] == p['cs'] and abs(w['f'] - p['f']) < 2]

        succeded_imm = len([1 for w, p in matches if "Decoded-D " in p['info']])
        succeded_ldpc = len([1 for w, p in matches if "Decoded-DL " in p['info']])
        succeded_bf_ldpc = len([1 for w, p in matches if "Decoded-DBL " in p['info']])
        succeded = succeded_imm + succeded_ldpc + succeded_bf_ldpc
        failed_bf_ldpc = len([1 for w, p in matches if "Failed-DBL " in p['info']])
        failed  = len([1 for w, p in matches if "Failed" in p['info']])
        starved  = len([1 for w, p in matches if not "Decoded" in p['info'] and not "Failed" in p['info']])
        total = succeded + failed + starved

        print(succeded_imm, succeded_ldpc, succeded_bf_ldpc, failed, starved, pc_str(succeded, total), pc_str(succeded_bf_ldpc, succeded_bf_ldpc + failed_bf_ldpc))
        
#        for w, p in matches[-50:]:
#            print(f"{w['cs']} {w['msg']:<25} {p['msg']:<25} {p['info']}")

        
except KeyboardInterrupt:
    print("\nStopping PyFT8 Rx")
    cycle_manager.running = False
    running = False


    



