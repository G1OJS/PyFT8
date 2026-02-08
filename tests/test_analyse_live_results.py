import pickle
import matplotlib.pyplot as plt
import numpy as np

def analyse(decodes, cyc):
    p_msgs = set([d['cs']+d['msg'] for d in decodes if d['decoder'] == 'PyFT8'])
    w_msgs = set([d['cs']+d['msg'] for d in decodes if d['decoder'] == 'WSJTX'])
    both_msgs = p_msgs.intersection(w_msgs)
    nw, np, nb = len(w_msgs), len(p_msgs), len(both_msgs)
    if(nw>0):            
        print(f"{cyc} W:{nw} P:{np}({np/nw:.1%}) B:{nb}({nb/nw:.1%})")

def tab_print(dd):
    sync_idx = dd['sync_idx'] if dd['decoder'] == 'PyFT8' else ''
    row = f"{dd['decoder']}, {dd['cs']} {dd['f']:4d} {dd['snr']:+04d} {dd['dt']:4.1f} {dd['td']:<4} {dd['msg']:<23} {sync_idx} "
    print(f"{row}")

def list_decodes(cyc):
    for d in [d for d in decodes if d['cs'] == cyc]:
        tab_print(d)

def list_cycle_stats():
    cycles = list(set([d['cs'] for d in decodes]))
    cycles.sort()
    for cyc in cycles[::-1]:
        decodes_cyc = [d for d in decodes if d['cs'] == cyc]
        analyse(decodes_cyc, cyc)
    analyse(decodes, "000000_000000")

def timings():
    p_td, w_td = [], []
    for p in decodes_p:
        w = [d for d in decodes_w if d['msg'] == p['msg'] and np.abs(float(p['td']) - float(d['td']))%15 < 5]
        if(len(w)):
           w_td.append(float(w[0]['td']) %15)
           p_td.append((float(p['td']) -float(w[0]['td'])) %15) 
    fig, ax = plt.subplots()
    ax.scatter(w_td, p_td)
    plt.show()
    
with open("live_decodes_vs_wsjtx.pkl", "rb") as f:
    decodes = pickle.load(f)
decodes_p =  [d for d in decodes if d['decoder'] == 'PyFT8']
decodes_w =  [d for d in decodes if d['decoder'] == 'WSJTX']

#list_decodes('260208_150100')
#list_cycle_stats()
timings()
