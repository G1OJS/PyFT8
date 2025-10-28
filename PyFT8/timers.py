import time
def tstrcyclestart_str(cycle_offset):
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(15*cycle_offset + 15*int(time.time() / 15)))

def tstrNow():
    return time.strftime("%H:%M:%S", time.gmtime(time.time()))

global last_timedLog
last_timedLog = 0
def timedLog(msg, silent = False):
    global last_timedLog
    with open ('PyFT8.log', 'w') as f:
        t = time.time()
        decs = f"{t-int(t):.2f}"
        decs = decs.replace('0.','')
        ts = f"{time.strftime('%H:%M:%S', time.gmtime(t))}.{decs}"
        if(last_timedLog):
            delta = t - last_timedLog
            ts += f" ({delta:+.2f})"
        else:
            ts += f" (=0.00)"
        last_timedLog = t
        s = f"{ts} {msg}"
        if (not silent): print(s)
        f.write(f"{s}\n")
