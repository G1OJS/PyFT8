import time
import threading
from PyFT8.comms_hub import config, events

CYCLE_LENGTH = 15

def sleep_until(cycle_seconds = 0):
    t_elapsed, t_remain, = time_in_cycle()
    sleep_time = cycle_seconds - t_elapsed
    if(sleep_time)>0:
        time.sleep(sleep_time)
    
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

def cycle_tick():
    t = (time.time() / CYCLE_LENGTH) % 2
    odd_even = ['even','odd'][int(t)]
    events.publish("cycle_start", odd_even)
    threading.Timer(15, cycle_tick).start()

sleep_until(0)
cycle_tick()

