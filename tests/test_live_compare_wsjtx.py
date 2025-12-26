
import threading
import time
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"
global pyftx_decodes, wsjtx_decodes

decodes = {}
decodes_lock = threading.Lock()

UID_FIELDS = ('cyclestart_str', 'call_a', 'call_b', 'grid_rpt')
COMMON_FIELDS = {'t_decode', 'snr', 'dt'}
PyFT8_FIELDS = {'sync_score', 'ncheck_initial', 'n_its', 'pass2', 'pass2_mets'}

running = True

def make_uid(d):
    return tuple(d[k] for k in UID_FIELDS)

def on_PyFT8_decode(c):
    decode_dict = {'decoder':'PyFT8', 'cyclestart_str':c.cyclestart_str,
                   'call_a':c.call_a, 'call_b':c.call_b, 'grid_rpt':c.grid_rpt,
                   't_decode':time.time(), 'snr':c.snr, 'dt':c.dt, 'sync_score':c.pipeline.sync.result.score,
                   'ncheck_initial':c.pipeline.ldpc.metrics.ncheck_initial, 'n_its': c.pipeline.ldpc.metrics.n_its,
                   'pass2':'osd' if c.pipeline.osd.success else '',
                   'pass2_mets': str([c.pipeline.osd.metrics.ncheck_initial, c.pipeline.osd.metrics.n_its,
                                      c.pipeline.osd.metrics.n_to_flip, c.pipeline.osd.metrics.n_flipped ]) if c.pipeline.osd.success else ''}
    on_decode(decode_dict)
           

def on_decode(decode_dict):
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
                           'dt':float(ls[5]), 'call_a':ls[7], 'call_b':ls[8], 'grid_rpt':ls[9], 'snr':ls[4]}
        except:
            pass
        if(decode_dict):
            on_decode(decode_dict)

def update_stats():
    last_ct = 0
    logfile = 'live_compare_rows.csv'

    heads = f"{'Cycle':>13} {'Call_a':>12} {'Call_b':>12} {'Grid_rpt':>8} {'Decoder':>7} {'tP':>7} {'tW':>7} {'dtP':>7} {'dtW':>7} {'sync':>7} {'nchk':>7} {'n_its':>7} {'pass2':>7}"
    with open(logfile, 'w') as f:
        f.write(f"{heads}\n")
        
    while running:
        time.sleep(1)
        ct = time.time() % 15
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

                    info = f"{tP} {tW} {dtP} {dtW}"
                    if ('PyFT8_t_decode' in d):
                        info = info + f" {d['PyFT8_sync_score']:7.1f} {d['PyFT8_ncheck_initial']:>7} {d['PyFT8_n_its']:>7} {d['PyFT8_pass2']:>7} {d['PyFT8_pass2_mets']}"

                    #if(decoder == 'BOTH '):
                    row = f"{uid_pretty} {decoder:>7} {info}"
                    print(row)
                    with open(logfile, 'a') as f:
                        f.write(f"{row}\n")
                pc = int(100*(nP+nB) / (nW+nB+0.001))
                print(f"WSJTX:{nW+nB}, PyFT8: {nP+nB} ({pc}%)")
                with open('live_compare_cycle_stats.csv', 'a') as f:
                    f.write(f"{nW},{nP},{nB}\n")

        last_ct = ct


threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path, on_decode,)).start()

threading.Thread(target=update_stats).start()    

cycle_manager = Cycle_manager(FT8, on_PyFT8_decode, onOccupancy = None, input_device_keywords = ['Microphone', 'CODEC'],
                              sync_score_thresh = 4, max_ncheck = 23, max_iters = 9, verbose = True)

with open('live_compare_cycle_stats.csv', 'w') as f:
    f.write("nWSJTX,nPyFT8,nBoth\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PyFT8 Rx")
        cycle_manager.running = False
        running = False


    



