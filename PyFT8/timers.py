import time
import threading
from PyFT8.signaldefs import FT8
import os

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

def cyclestart_str():
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(CYCLE_LENGTH * int(time.time() / CYCLE_LENGTH)))

def timestamp_bundle():
    """Return all forms of time once so all logs stay consistent."""
    t = time.time()
    return {
        "t": t,                               # raw unix timestamp
        "cycle_str": cyclestart_str(),        # 'HHMMSS_xxxxxx'
        "t_elapsed": t % CYCLE_LENGTH         # seconds into cycle
    }

def timedLog(msg, silent=False, logfile=None):
    ts = timestamp_bundle()
    if not silent:
        print(f"{ts['cycle_str']} {ts['t_elapsed']:.1f} {msg}")
    if logfile:
        with open(logfile, 'a') as f:
            f.write(f"{ts['cycle_str']},{ts['t_elapsed']:.3f},{ts['t']:.3f},{msg}\n")

logs_opened=[]
def timedLogCSV(stats_dict, filename):
    global logs_opened
    ts = timestamp_bundle()
    row_dict = {
        "cycle_str": ts["cycle_str"],
        "t_elapsed": round(ts["t_elapsed"], 3),
        "unix_ts":   round(ts["t"], 3),
        **stats_dict
    }
    
    if(not filename in logs_opened):
        with open(filename, 'w') as f:
            f.write(','.join(row_dict.keys()) + "\n")
        logs_opened.append(filename)
        
    with open(filename, 'a') as f:
        f.write(','.join(str(v) for v in row_dict.values()) + "\n")

