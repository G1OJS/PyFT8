import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
from PyFT8.time_utils import tlog

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

def tab_print(dd):
    row = f"{dd['decoder']}, {dd['cs']} {dd['f']:4d} {dd['snr']:+04d} {dd['dt']:4.1f} {dd['td']:<4} {dd['msg']:<23} "
    tlog(f"{row}")    

def run_live_test():
    decodes = []
    t_last_decode = 0

    def on_decode(dd):
        t_last_decode = time.time()
        decodes.append(dd)

    cycle_manager = Cycle_manager(FT8, on_decode, input_device_keywords = ['Microphone', 'CODEC'], verbose = False)
    wsjtx_all_tailer = Wsjtx_all_tailer(on_decode, silent = True)
    while True:
        time.sleep(1)
        if(time.time() - t_last_decode > 5):
            t_last_decode = time.time()
            cycles = set([d['cs'] for d in decodes])
            if(len(cycles)>1):
                curr_cycle = list(cycles)[-2]
                decodes = [d for d in decodes if d['cs'] == curr_cycle]
                for dd in decodes:
                    tab_print(dd)
            


run_live_test()
