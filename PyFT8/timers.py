import time
import threading

CYCLE_LENGTH = 15

def sleep_until(cycle_seconds = 0):
    t_elapsed, t_remain, = time_in_cycle()
    sleep_time = cycle_seconds - t_elapsed
    if(sleep_time)>0:
        time.sleep(sleep_time)
    else:
        time.sleep(sleep_time + CYCLE_LENGTH)

def tnow():
    return time.time()

def QSO_dnow_tnow():
    t = time.gmtime(tnow())
    return time.strftime("%Y%m%d",t), time.strftime("%H%M%S", t)
    
def sleep(secs):
    if(secs>0):
        time.sleep(secs)

def time_in_cycle():
    t_elapsed = (time.time() % CYCLE_LENGTH)
    t_remaining = CYCLE_LENGTH - t_elapsed 
    return t_elapsed, t_remaining

def cyclestart_str(cycle_offset):
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(CYCLE_LENGTH * cycle_offset + CYCLE_LENGTH * int(time.time() / 15)))

def timedLog(msg, silent = False, logfile = 'PyFT8.log'):
    global last_timedLog
    with open (logfile, 'a') as f:
        t = time.time()
        decs = f"{t-int(t):.2f}"
        decs = decs.replace('0.','')
        ts = f"{time.strftime('%H:%M:%S', time.gmtime(t))}.{decs}"
        s = f"{ts} {msg}"
        if (not silent):
            print(f"Log to {logfile}: {s}")
        f.write(f"{s}\n")

def odd_even_now():
    t = (time.time() / CYCLE_LENGTH) % 2
    return['even','odd'][int(t)]  

