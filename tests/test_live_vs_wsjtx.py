import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
from PyFT8.time_utils import tlog
import pickle

class Wsjtx_all_tailer:
    
    def __init__(self, on_decode, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt", silent = True):
        self.all_file = all_file
        self.on_decode = on_decode
        self.silent = silent
        threading.Thread(target = self.run).start()

    def run(self):
        def follow():
            with open(self.all_file, "r") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    yield line.strip()
        for line in follow():
            ls = line.split()
            try:
                cs, freq, dt, snr = ls[0], int(ls[6]), float(ls[5]), int(ls[4])
                msg = f"{ls[7]} {ls[8]} {ls[9]}"
                td = f"{time.time() %60:4.1f}"
                self.on_decode({'cs':cs, 'decoder':'WSJTX', 'f':int(freq), 'msg':msg, 'dt':dt, 'snr':snr, 'td':td})
            except:
                if(not self.silent):
                    print(f"Wsjtx_tailer error in line '{line}'")


def analyse(decodes, cyc):
    p_msgs = set([d['cs']+d['msg'] for d in decodes if d['decoder'] == 'PyFT8'])
    w_msgs = set([d['cs']+d['msg'] for d in decodes if d['decoder'] == 'WSJTX'])
    both_msgs = p_msgs.intersection(w_msgs)
    nw, np, nb = len(w_msgs), len(p_msgs), len(both_msgs)
    if(nw>0):            
        print(f"{cyc} W:{nw} P:{np}({np/nw:.1%}) B:{nb}({nb/nw:.1%})")

def tab_print(dd):
    row = f"{dd['decoder']}, {dd['cs']} {dd['f']:4d} {dd['snr']:+04d} {dd['dt']:4.1f} {dd['td']:<4} {dd['msg']:<23} "
    tlog(f"{row}")    

def run_live_test():
    from collections import Counter

    decodes = []
    t_last_decode = 0
    started = False

    def on_decode(dd):
        decodes.append(dd)

    cycle_manager = Cycle_manager(FT8, on_decode, input_device_keywords = ['Microphone', 'CODEC'], verbose = False)
    wsjtx_all_tailer = Wsjtx_all_tailer(on_decode, silent = True)
    wait = 4 + 15 - time.time()%15
    time.sleep(wait)
    
    while True:
        time.sleep(15)
        if(not started):
                decoders = set([d['decoder'] for d in decodes])
                if(len(decoders) == 2):
                    decodes = []
                    started = True
        if(started):          
            print("================================================")
            cycles = list(set([d['cs'] for d in decodes]))
            cycles.sort()
            for cyc in cycles[::-1]:
                decodes_cyc = [d for d in decodes if d['cs'] == cyc]
                analyse(decodes_cyc, cyc)
            analyse(decodes, "000000_000000")

            with open("live_decodes_vs_wsjtx.pkl", "wb") as f:
                pickle.dump(decodes,f)

run_live_test()
