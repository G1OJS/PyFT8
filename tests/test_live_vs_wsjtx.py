import numpy as np
import threading
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.cycle_decoder import start_cycle_decoder
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers

PyFT8_file = "pyft8.txt"
wsjtx_file = "wsjtx.txt"

global lw_tot, lp_tot, best_snr_alltime
lw_tot, lp_tot = 0, 0
best_snr_alltime = 50

def wsjtx_tailer():
    def follow(path):
        with open(path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    timers.sleep(0.2)
                    continue
                yield line.strip()
                
    for line in follow(r"C:\Users\drala\AppData\Local\WSJT-X\ALL.txt"):
        with open(wsjtx_file, 'a') as f:
            f.write(f"{line}\n")

def wsjtx_compare(wsjtx_file, PyFT8_file):
    global lw_tot, lp_tot, best_snr_alltime

    import sys
    color = sys.stdout.shell

    with open(wsjtx_file, 'r') as f:
        lines = f.readlines()
    cyclestamp = lines[-1][:14]
    wsjt_lines = [line for line in lines if line.startswith(cyclestamp)]

    with open(PyFT8_file, 'r') as f:
        PyFT8_lines = f.readlines()

    wsjt_patterns =[]
    for l in wsjt_lines:
        wsjt_patterns.append(l[48:].replace(' ',''))
        
    PyFT8_patterns =[]
    for l in PyFT8_lines:
        PyFT8_patterns.append(l[48:].replace(' ',''))

    best_snr = 50
    def linefreq(line): return int(line[43:48])
    wsjt_lines.sort(key = linefreq)
    for i, l in enumerate(wsjt_lines):
        if(wsjt_patterns[i] in PyFT8_patterns):
            color.write(f" BOTH: {l}", "STRING")
        else:
            color.write(f"WSJTX: {l}", "KEYWORD")
        if(wsjt_patterns[i] in PyFT8_patterns):
            snr = int(l[34:37])
            if (snr<best_snr): best_snr = snr

    for i, l in enumerate(PyFT8_lines):
        if(PyFT8_patterns[i] not in wsjt_patterns): 
            color.write(f"PyFT8: {l}", "COMMENT")

    lw, lp = len(wsjt_lines), len(PyFT8_lines)
    lw_tot += lw
    lp_tot += lp
    if(best_snr < best_snr_alltime): best_snr_alltime = best_snr    
    timers.timedLog(f"This Cycle: WSJTX:{lw} PyFT8:{lp} -> {lp/(1e-12+lw):.0%} best snr = {best_snr}")
    timers.timedLog(f"All cycles: WSJTX:{lw_tot} PyFT8:{lp_tot} -> {lp_tot/(1e-12+lw_tot):.0%} best snr = {best_snr_alltime}")
    
def reset_compare():
    with open(wsjtx_file, 'w') as f:
        f.write("")
    with open(PyFT8_file, 'w') as f:
        f.write("")

def onFinished():
    wsjtx_compare(wsjtx_file,PyFT8_file)
    reset_compare()

def onDecode(decode):
    if(not decode): return
    all_txt_line = decode['all_txt_line']
    with open(PyFT8_file, "a") as f:
        f.write(all_txt_line + "\n")

print("Running, waiting for messages")
reset_compare()        
threading.Thread(target=wsjtx_tailer).start()
start_cycle_decoder(onDecode = onDecode, onFinished = onFinished)



    

