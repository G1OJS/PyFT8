import time
import threading
from PyFT8.signaldefs import FT8

CYCLE_LENGTH = FT8.cycle_seconds

def tnow():
    return time.time()

def tnow_str(offset_secs = 0):
    return time.strftime("%H%M%S", time.gmtime(tnow()+offset_secs))

def QSO_dnow_tnow():
    t = time.gmtime(tnow())
    return time.strftime("%Y%m%d",t), time.strftime("%H%M%S", t)
    
def sleep(secs):
    if(secs>0):
        time.sleep(secs)

def cyclestart_str(cycle_offset):
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(CYCLE_LENGTH * cycle_offset + CYCLE_LENGTH * int(time.time() / 15)))

def timedLog(msg, silent = False, logfile = None):
    t = time.time()
    time_str = cyclestart_str(0)
    t_elapsed = t % CYCLE_LENGTH
    time_str = f"{time_str}_{t_elapsed:.1f}"
    lf = f"Log to {logfile}:" if logfile else ''
    if (not silent):
        print(f"{time_str} {lf} {msg}")
    if(logfile):
        with open (logfile, 'a') as f:
            f.write(f"{time_str} {msg}\n")



