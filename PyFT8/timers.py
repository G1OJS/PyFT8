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

last_timedLog = False
def timedLog(msg, silent = False, logfile = None):
    global last_timedLog
    t = time.time()
    seconds_since_last_msg = t - last_timedLog if last_timedLog else 0
    time_str = f"{time.strftime('%H:%M:%S')}"
    t_elapsed = t % CYCLE_LENGTH
    time_str = f"{time_str} ({t_elapsed:4.1f})"
    lf = f"Log to {logfile}:" if logfile else ''
    output_str = f"{time_str} {lf} {msg}"
    if (not silent):
        print(f"{output_str}")
    if(logfile):
        with open (logfile, 'a') as f:
            f.write(f"{output_str}\n")
    if(not silent): last_timedLog = t


