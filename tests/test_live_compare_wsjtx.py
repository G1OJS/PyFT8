
import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"

cycles = []
decodes = []
decodes_lock = threading.Lock()
    
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

def pc_str(x,y):
    return "{}" if y == 0 else int(100*x/y)
    
def update_stats(cand_info):
    global nPyFT8
    output = []
    latest_cycle_decodes = [d for d in decodes if d['cyclestart_str'] == cycles[-1]]
    print(len(latest_cycle_decodes))
    for dd in latest_cycle_decodes:

        f_idx = int(int(dd['freq']) / cycle_manager.spectrum.df)
        for i in [0,1,2]:
            ci = cand_info[f_idx +i]
        output.append(f"{dd['cyclestart_str']} {dd['msg']:<22} {ci}")

    w = output
    p = [r for r in output if "Decoded" in r]
    pI = [r for r in output if "Decoded-D" in r]
    pL =  [r for r in output if "Decoded-DL" in r] 
    pB =  [r for r in output if "Decoded-DBL" in r]
    pBf = [r for r in output if "Failed-DBL" in r]
    pF = [r for r in output if "Failed" in r]
    pM = [r for r in output if not "Failed" in r and not "Decoded" in r]
    
    for row in output:
        print(row)

    nP, nW = len(p), len(w)
    pc = pc_str(nP, nW)
    pcBitFlip = pc_str(len(pB), len(pB)+len(pBf))
    print(f"WSJTX:{nW}, PyFT8:{nP} ({pc}%) Flip success = {pcBitFlip}%\n")
    with open('live_compare_cycle_stats.csv', 'a') as f:
        f.write(f"{len(w)},{len(pI)},{len(pB)},{len(pF)},{len(pM)}\n")
        
with open('live_compare_cycle_stats.csv', 'w') as f:
    f.write("nWSJTX,nPyFT8_Instant,nPyFT8_LDPC,nPyFT8_BitFlipLDPC,nPyFT8_Failed,nPyFT8_missed,PyFT8_pc\n")
    
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


    



