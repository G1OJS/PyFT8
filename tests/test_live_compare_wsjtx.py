
import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"
global pyftx_decodes, wsjtx_decodes

decodes = {}
decodes_lock = threading.Lock()

UID_FIELDS = ('cyclestart_str', 'call_a', 'call_b', 'grid_rpt')
COMMON_FIELDS = {'t_decode', 'snr', 'dt', 'freq'}
PyFT8_FIELDS = {'sync_score', 'info_str'}

running = True
pyft8_started = False

def make_uid(d):
    return tuple(d[k] for k in UID_FIELDS)

def on_PyFT8_decode(c):
    global pyft8_started
    pyft8_started = True
    decode_dict = {'decoder':'PyFT8', 'cyclestart_str':c.cyclestart_str,
                   'call_a':c.call_a, 'call_b':c.call_b, 'grid_rpt':c.grid_rpt, 'sync_score':f"{c.sync_score:5.2f}",
                   't_decode':time.time(), 'snr':c.snr, 'dt':c.dt, 'freq':c.fHz,
                   'info_str':f"{c.sync_score:5.2f}; {c.info_str}" }
    on_decode(decode_dict)
           
def on_decode(decode_dict):
    if not pyft8_started: return
    uid = make_uid(decode_dict)
    decoder = decode_dict['decoder']
    with decodes_lock:
        if uid not in decodes:
            decodes[uid] = {}
        for field in COMMON_FIELDS:
            decodes[uid].update({f"{decoder}_{field}": decode_dict[field]})
        decodes[uid].update({'decoder':decoder})
        if(decoder == 'PyFT8'):
            for field in PyFT8_FIELDS:
                decodes[uid].update({f"{decoder}_{field}": decode_dict[field]})

def align_call(call):
    # whilst PyFT8 not decoding hashed calls and /P etc
    if("<" in call):
        call = "<...>"
    if("/P" in call):
        call = call.replace("/P","")
    return call

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
            decode_dict = {'cyclestart_str':ls[0], 'decoder':'WSJTX', 'freq':ls[6], 't_decode':time.time(),
                           'dt':float(ls[5]), 'call_a':align_call(ls[7]), 'call_b':align_call(ls[8]), 'grid_rpt':ls[9], 'snr':ls[4]}
        except:
            pass
        if(decode_dict):
            on_decode(decode_dict)

def update_stats():
    last_ct = 0
    heads = f"{'Cycle':>13} {'Call_a':>12} {'Call_b':>12} {'Grid_rpt':>8} {'Decoder':>7} {'fP':>7} {'fW':>7} {'dtP':>7} {'dtW':>7} {'tP':>7} {'tW':>7} {'info':<7}"
    nPtot, nWtot, nBtot = 0, 0, 0
    
    while running:
        time.sleep(1)
        ct = (time.time()-3) % 15
        if ct < last_ct:
            now = time.time()

            with decodes_lock:
                expired = []
                for uid in decodes:
                    o = decodes[uid]
                    if(now - o.get('PyFT8_t_decode',1e40) > 30 or now - o.get('WSJTX_t_decode',1e40) > 30):
                        expired.append(uid)
                for uid in expired:
                    del decodes[uid]

            if(len(decodes)):
                latest_cycle = list(decodes.keys())[-1][0]
                latest_cycle_uids = [uid for uid in decodes.keys() if uid[0] == latest_cycle]
                nP = nW = nB = 0
                print(heads)
                for uid in latest_cycle_uids:
                    uid_pretty = f"{uid[0]} {uid[1]:>12} {uid[2]:>12} {uid[3]:>8}"
                    d = decodes[uid]
                    decoder = d['decoder']
                    def cyt(t): return t %15
                    tP = dtP = tW = dtW = f"{'-':>7}"
                    if('PyFT8_t_decode' in d): tP, dtP = f"{cyt(d['PyFT8_t_decode']):7.2f}", f"{d['PyFT8_dt']:7.2f}"
                    if('WSJTX_t_decode' in d): tW, dtW = f"{cyt(d['WSJTX_t_decode']):7.2f}", f"{d['WSJTX_dt']:7.2f}"
                    
                    if ('PyFT8_t_decode' in d and not 'WSJTX_t_decode' in d): nP +=1
                    if (not 'PyFT8_t_decode' in d and 'WSJTX_t_decode' in d): nW +=1
                    
                    if ('PyFT8_t_decode' in d and 'WSJTX_t_decode' in d):
                        decoder = 'BOTH '
                        nB +=1

                    info = f"{tP} {tW} {dtP} {dtW}  "
                    if ('PyFT8_t_decode' in d):
                        info = info + f" {d['PyFT8_info_str']}"

                    if (not 'PyFT8_t_decode' in d and 'WSJTX_t_decode' in d):
                        f_idx = int(int(get('WSJTX_freq')) / spec.df)
                        ci = cycle_manager.cand_info[f_idx]
                        info = info + "["+ci+"]"

                    def get(key):
                        return d[key] if key in d else ''

                    row = f"{uid_pretty} {decoder:>7} {get('PyFT8_freq'):>7} {get('WSJTX_freq'):>7} {info}"
                    print(row)
                pc = int(100*(nP+nB) / (nW+nB+nP+0.001))
                print(f"WSJTX:{nW+nB}, PyFT8: {nP+nB} ({pc}%)")
                with open('live_compare_cycle_stats.csv', 'a') as f:
                    f.write(f"{nW},{nP},{nB}\n")
                nPtot += nP
                nBtot += nB
                nWtot += nW
                pc = int(100*(nPtot+nBtot) / (nPtot+nWtot+nBtot+0.001))
                print(f"All time: WSJTX:{nWtot+nBtot}, PyFT8: {nPtot+nBtot} ({pc}%)")

        last_ct = ct



with open('live_compare_cycle_stats.csv', 'w') as f:
    f.write("nWSJTX,nPyFT8,nBoth\n")
    
threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path, on_decode,)).start()
threading.Thread(target=update_stats).start()    
cycle_manager = Cycle_manager(FT8, on_PyFT8_decode, onOccupancy = None,
                              input_device_keywords = ['Microphone', 'CODEC'], verbose = True)

spec = cycle_manager.spectrum

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping PyFT8 Rx")
    cycle_manager.running = False
    running = False


    



