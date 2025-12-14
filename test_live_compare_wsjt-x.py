
# WORK IN PROGRESS #

import threading
import PyFT8.timers as timers
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8

all_txt_path = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"
global pyftx_decodes, wsjtx_decodes

decodes = {}
decodes_lock = threading.Lock()

UID_FIELDS = ('cyclestart_str', 'call_a', 'call_b', 'grid_rpt')
COMMON_FIELDS = {'t_decode', 'snr'}
PyFT8_FIELDS = {'n_its', 'ncheck_initial', 'ldpc_time'}

def make_uid(d):
    return tuple(d[k] for k in UID_FIELDS)

def update_decodes(uid, decode_dict):
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

def on_decode(decode_dict):
    uid = make_uid(decode_dict)
    update_decodes(uid, decode_dict)


def wsjtx_all_tailer(all_txt_path, on_decode):
    def follow():
        with open(all_txt_path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    timers.sleep(0.2)
                    continue
                yield line.strip()
    for line in follow():
        ls = line.split()
        decode_dict = False
        try:
            decode_dict = {'cyclestart_str':ls[0], 'decoder':'WSJTX', 'freq':ls[6], 't_decode':timers.tnow(),
                           'dt':ls[5], 'call_a':ls[7], 'call_b':ls[8], 'grid_rpt':ls[9], 'snr':ls[4]}
        except:
            pass
        if(decode_dict):
            on_decode(decode_dict)

def update_stats():
    last_ct = 0

    while True:
        timers.sleep(1)
        ct = timers.tnow() % 15
        if ct < last_ct:
            now = timers.tnow()

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
                print(f"{'Cycle':>13} {'Call_a':>12} {'Call_b':>12} {'Grid_rpt':>8} {'Decoder':>7} {'t(P)':>7} {'t(W)':>7} {'t(P)-t(W)':>7} {'n_its':>7} {'nchk':>7} {'t_ldpc':>7}")
                for uid in latest_cycle_uids:
                    uid_pretty = f"{uid[0]} {uid[1]:>12} {uid[2]:>12} {uid[3]:>8}"
                    d = decodes[uid]
                    decoder = d['decoder']
                    def cyt(t): return (t+7) %15 - 7
                    if ('PyFT8_t_decode' in d and 'WSJTX_t_decode' in d):
                        decoder = 'BOTH '
                        tP, tW = d['PyFT8_t_decode'], d['WSJTX_t_decode']
                        info = f"{cyt(tP):7.2f} {cyt(tW):7.2f} {tP - tW:7.2f}"
                        nB +=1
                    if ('PyFT8_t_decode' in d and not 'WSJTX_t_decode' in d):
                        tP = d['PyFT8_t_decode']
                        info = f"{cyt(tP):7.2f}                "
                        nP +=1
                    if (not 'PyFT8_t_decode' in d and 'WSJTX_t_decode' in d):
                        tW = d['WSJTX_t_decode']
                        info = f"        {cyt(tW):7.2f}        "
                        nW +=1
                    if ('PyFT8_t_decode' in d):
                        info = info + f" {d['PyFT8_n_its']:>7} {d['PyFT8_ncheck_initial']:>7} {float(d['PyFT8_ldpc_time'])*1000:7.0f}ms"


                    if(decoder == 'BOTH '):
                        print(f"{uid_pretty} {decoder:>7} {info}")
                pc = int(100*(nP+nB) / (nW+nB))
                print(f"WSJTX:{nW+nB}, PyFT8: {nP+nB} ({pc}%)")

        last_ct = ct

            

cycle_manager = Cycle_manager(FT8, on_decode, onOccupancy = None, input_device_keywords = ['Microphone', 'CODEC'],
                              max_iters = 10, max_stall = 10, max_ncheck = 35, timeout = 0.05, 
                              sync_score_thresh = 2.2, thread_PyFT8_decode_manager = True) 

threading.Thread(target=wsjtx_all_tailer, args = (all_txt_path, on_decode,)).start()

threading.Thread(target=update_stats).start()

    



