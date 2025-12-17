
import numpy as np
from PyFT8.waterfall import Waterfall
import PyFT8.timers as timers
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

global decoded_candidates
decoded_candidates = []
first = True

def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['        Cycle', 'demap','ldpc','decode', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx', 'ncheck', 'Hz']
        print(''.join([f"{t:>8} " for t in heads]))
    dd = c.decode_dict
    vals = [f"{dd['cyclestart_str']} {c.demap_returned %15:8.2f} {c.ldpc_returned %15:8.2f} {timers.tnow() %15:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{dd['sync_score']:>5.2f}",  f"{dd['snr']:5.0f}", dd['t0_idx'], dd['f0_idx'], dd['ncheck_initial'], dd['freq']]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)

import pickle
if(0):
    wav_file = "210703_133430.wav"
    cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = wav_file, 
                              max_iters = 35,  max_ncheck = 30,
                              sync_score_thresh = 3.2, max_cycles = 2, return_candidate = True)
    while cycle_manager.running:
        timers.sleep(0.5)
    spectrum = cycle_manager.spectrum
    with open('210703_133430.pkl', 'wb') as f:
        pickle.dump(spectrum,f)
else:
    with open('210703_133430.pkl', 'rb') as f:
        spectrum = pickle.load(f)



from PyFT8.FT8_demodulator import FT8Demodulator, Candidate
from PyFT8.decode174_91_v5_5 import LDPC174_91
from PyFT8.FT8_unpack import FT8_unpack

demod = FT8Demodulator(FT8)
ldpc = LDPC174_91(max_iters = 90, max_ncheck = 55)

candidates = []
n_hops_costas = np.max(spectrum.hop_idxs_Costas)
f0_idxs = range(spectrum.nFreqs - spectrum.candidate_size[1])

def demap_candidate(c):
    origin = c.origin
    synced_grid_complex = c.synced_grid_complex.reshape(FT8.num_symbols, 3, FT8.tones_persymb, 3)
    synced_grid_pwr = np.abs(synced_grid_complex[:,0,:,1])**2 
    p = synced_grid_pwr[FT8.payload_symb_idxs] / np.max(synced_grid_pwr)
    llr0 = np.log(np.max(p[:,[4,5,6,7]], axis=1)) - np.log(np.max(p[:,[0,1,2,3]], axis=1))
    llr1 = np.log(np.max(p[:,[2,3,4,7]], axis=1)) - np.log(np.max(p[:,[0,1,5,6]], axis=1))
    llr2 = np.log(np.max(p[:,[1,2,6,7]], axis=1)) - np.log(np.max(p[:,[0,3,4,5]], axis=1))
    llr = np.column_stack((llr0, llr1, llr2)).ravel()
    return llr, 0

#wf = Waterfall(spectrum)
#wf.update_main(candidates=candidates)


wsjt_freqs = [2571, 2157, 1197, 641, 723, 1648, 2852, 590, 2695 ,400, 2733, 2522, 2546, 2238, 466, 1513, 2039, 472, 2280]
wsjt_idxs = [int(f/spectrum.df) for f in wsjt_freqs]

zgrid = spectrum.fine_grid_complex
eps = 1e-12
# 
look_at = [1234, 1035, 574, 307, 347, 791, 1368, 282, 1293, 192, 1311, 1210, 1222, 1074, 223, 726, 978, 226, 1094]
#look_at = [1311]

for f0_idx in look_at:
    c_zgrid = zgrid[: n_hops_costas + demod.slack_hops, f0_idx:f0_idx + demod.fbins_per_signal]
    csync = spectrum._csync
    c_pgrid = np.abs(c_zgrid)**2
    max_pwr = np.max(c_pgrid)
    c_pgrid = c_pgrid / (max_pwr + eps)
    best = (0, -1e30)
    for t0_idx in range(demod.slack_hops - n_hops_costas):
        test = (t0_idx, float(np.dot(c_pgrid[t0_idx + spectrum.hop_idxs_Costas ,  :].ravel(), spectrum._csync.ravel())))
        if test[1] > best[1]:
            best = test
    c = Candidate(spectrum)
    c.sync_score = best[1]
    c.origin = (best[0], f0_idx, spectrum.dt * t0_idx, spectrum.df * (f0_idx + 1))
    c.synced_grid_complex = spectrum.fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0], c.origin[1]:c.origin[1]+c.size[1]]
    c.llr, c.snr = demap_candidate(c)
    ldpc.decode(c)
    c.decode_dict={'call_a':'??','call_b':'??'}
    message_parts = FT8_unpack(c.payload_bits)
    if(message_parts):
        c.decode_dict={'call_a':message_parts[0],'call_b':message_parts[1]}
        print(c.origin[0], message_parts, c.sync_score, c.ncheck_initial)

#wf.show_zoom(candidates=candidates)



