WAV =  "210703_133430.wav"

import numpy as np
import time
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = []
unique_decodes_set = set()
unique_decodes = []
first = True

wsjt_freqs = [2571,1197,2157,590,723,2695,641,466,1649,2734,400,2853,472,2522]

def onRollover(cands):
    for c in cands:
        if(any([f for f in wsjt_freqs if abs(c.fHz-f)<2])):
            onDecode(c)

def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['        Cycle', 'Rx call', 'Tx call', 'GrRp',  'snr', 'f', 'f_idx']
        print(''.join([f"{t:>8} " for t in heads]))
    def t_fmt(t):return f"{t %15:8.2f}" if t else f"{'-':>8}"
    vals = [f"{c.cyclestart_str} ", getattr(c, 'call_a',''), getattr(c, 'call_b',''), getattr(c, 'grid_rpt',''),f"{c.snr:5.0f}", c.fHz, c.f0_idx]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)
    if(c.msg):
        if not c.msg in unique_decodes_set:
            unique_decodes_set.add(c.msg)
            unique_decodes.append(c)

cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, onCandidateRollover = onRollover,
                          audio_in_wav = WAV,  verbose = False, max_cycles = 2)

while cycle_manager.running:
    time.sleep(0.5)
time.sleep(2)

print(f"DONE. {len(list(unique_decodes_set))} unique decodes.")
for d in list(unique_decodes_set):
    print(d)


