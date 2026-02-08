import time

def cyclestart_str(t, cycle_seconds = 15):
    cyclestart_time = cycle_seconds * int(t / cycle_seconds)
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

def cycle_time(cycle_seconds = 15):
    return time.time() % cycle_seconds

def tlog(txt, verbose = True):
    if(verbose):
        print(f"{cyclestart_str(time.time())} {cycle_time():5.2f} {txt}")
