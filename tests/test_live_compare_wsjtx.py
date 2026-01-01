
import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"

cycles = []
decodes = []
decodes_lock = threading.Lock()
nPtot, nBtot, nWtot = 0,0,0

running = True

def on_decode(dd):
    pass

def wsjtx_all_tailer(all_txt_path, on_decode):
    def follow():
        with open(all_txt_path, "r") as f:
            f.seek(0, 2)
            while running:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()
    for line in follow():
        ls = line.split()
        decode_dict = False
        try:
            if(not ls[0] in cycles): cycles.append(ls[0])
            dd = {'cyclestart_str':ls[0], 'decoder':'WSJTX', 'freq':ls[6], 't_decode':time.time(),
                  'dt':float(ls[5]), 'msg':f"{ls[7]} {ls[8]} {ls[9]}", 'snr':ls[4]}
            decodes.append(dd)
        except:
            pass

def update_stats(cand_info):
    nP, nW, nB = 0, 0, 0
    nF = 0
    latest_cycle_decodes = [d for d in decodes if d['cyclestart_str'] == cycles[-1]]
    print(len(latest_cycle_decodes))
    for dd in latest_cycle_decodes:
        nW +=1
        f_idx = int(int(dd['freq']) / cycle_manager.spectrum.df)
        for i in [0,1,2]:
            ci = cand_info[f_idx +i]
            if("Decoded" in ci):
                nB +=1
                nW -=1
                if("F:" in ci): nF +=1
                break
        print(f"{dd['cyclestart_str']} {dd['msg']:<25} {ci}")

    pc = int(100*(nP+nB) / (nW+nB+nP+0.001))
    print(f"WSJTX:{nW}, PyFT8: {nP} ({pc}%) Flip success = {nF}")
    with open('live_compare_cycle_stats.csv', 'a') as f:
        f.write(f"{nW},{nP},{nB}\n")
    global nPtot, nWtot, nBtot
    nPtot += nP
    nBtot += nB
    nWtot += nW
    pc = int(100*(nPtot+nBtot) / (nPtot+nWtot+nBtot+0.001))
    print(f"All time: WSJTX:{nWtot+nBtot}, PyFT8: {nPtot+nBtot} ({pc}%)")

with open('live_compare_cycle_stats.csv', 'w') as f:
    f.write("nWSJTX,nPyFT8,nBoth\n")
    
threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path, on_decode,)).start()   
cycle_manager = Cycle_manager(FT8, on_decode, onOccupancy = None, update_stats = update_stats,
                              input_device_keywords = ['Microphone', 'CODEC'], verbose = True)


try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping PyFT8 Rx")
    cycle_manager.running = False
    running = False


    



