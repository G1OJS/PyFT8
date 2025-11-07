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

def tnow_str(offset_secs = 0):
    return time.strftime("%H%M%S", time.gmtime(tnow()+offset_secs))

def QSO_dnow_tnow():
    t = time.gmtime(tnow())
    return time.strftime("%Y%m%d",t), time.strftime("%H%M%S", t)
    
def sleep(secs):
    if(secs>0):
        time.sleep(secs)

def time_in_cycle(odd_even = 'next'):
    cycle_offset = CYCLE_LENGTH if(odd_even == odd_even_now()) else 0
    t_elapsed = (time.time() % CYCLE_LENGTH) - cycle_offset
    t_remaining = CYCLE_LENGTH - t_elapsed
    return t_elapsed, t_remaining

def cyclestart_str(cycle_offset):
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(CYCLE_LENGTH * cycle_offset + CYCLE_LENGTH * int(time.time() / 15)))

last_timedLog = False
def timedLog(msg, silent = False, logfile = 'PyFT8.log'):
    global last_timedLog
    with open (logfile, 'a') as f:
        t = time.time()
        seconds_since_last_msg = t - last_timedLog if last_timedLog else 0
        decimal_seconds = f"{t-int(t):.2f}"
        decimal_seconds = decimal_seconds.replace('0.','')
        time_str = f"{time.strftime('%H:%M:%S', time.gmtime(t))}.{decimal_seconds} ({seconds_since_last_msg:+04.2f})"
        output_str = f"{time_str} {msg}"
        if (not silent):
            print(f"Log to {logfile}: {output_str}")
        f.write(f"{output_str}\n")
        last_timedLog = t

def odd_even_now(from_click = False, swap = False):
    t_grace = 0 if(not from_click) else CYCLE_LENGTH/2
    t = ((time.time() + t_grace) / CYCLE_LENGTH) % 2
    if(swap): t = 1-t
    cycle = ['even','odd'][int(t)]
    timedLog(f"[odd_even_now] cycle is {cycle}")
    return cycle


def test():
    while True:
        sleep(1)
        print(tnow_str(), time_in_cycle('odd'))
       # cycle = odd_even_now(from_click = True)
       # _, t_remain = time_in_cycle(cycle)
       # print(tnow_str(), cycle, t_remain )

#test()
