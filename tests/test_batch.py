
import numpy as np
from PyFT8.spectrum import Spectrum
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
from PyFT8.time_utils import global_time_utils
import time
import pickle

global old_baseline

def run_offline(dataset, output_stub, freq_range):
    spectrum = Spectrum(FT8, 12000, 3100, 4, 2)
    spectrum.audio_in.load_wav(dataset+".wav")
    f0_idxs = range(int(freq_range[0]/spectrum.df),
                        min(spectrum.nFreqs - spectrum.fbins_per_signal, int(freq_range[1]/spectrum.df)))
    results = []
    msgs = []
    candidates = spectrum.search(f0_idxs, '000000_000000', 0)
    candidates = candidates + spectrum.search(f0_idxs, '000000_000000', 1)
    
    t0 = time.time()
    for c in candidates:
        c.demap(spectrum)
    candidates.sort(key = lambda c: -c.llr_sd)
    
    n_decodes = 0
    for c in candidates:
        c.decode()
        dd = c.decode_dict
        if(dd['msg'] and not dd['msg'] in msgs):
            msgs.append(dd['msg'])
            row = f"000000 {dd['snr']:3d} {dd['dt']:3.1f} {dd['f']:4d} ~ {dd['msg']:<23} {dd['sync_idx']} {dd['decode_path']}"
            print(row)
            results.append(row)
            n_decodes +=1
            
    decoding_time = time.time()-t0
    print(f"{n_decodes} decodes in {decoding_time:5.2f}s")
    
    with open(dataset + output_stub, "w") as f:
        for r in results:
            f.write(f"{r}\n")

    return n_decodes, decoding_time

def run(dataset, output_stub, freq_range):
    decodes = []
    results = []
    
    def on_decode(dd):
        decodes.append(dd)
        row = f"000000 {dd['snr']:3d} {dd['dt']:3.1f} {dd['f']:4d} ~ {dd['msg']:<23} {dd['sync_idx']} {dd['decode_path']}"
      #  print(row)
        results.append(row)

    cycle_manager = Cycle_manager(FT8, on_decode, wav_input = dataset+".wav", verbose = False)
    t0 = time.time()

    while not cycle_manager.spectrum.audio_in.wav_finished:
        time.sleep(0.5)
    n_decodes = len(decodes)
    
    with open(dataset + output_stub, "w") as f:
        for r in results:
            f.write(f"{r}\n")

    return n_decodes, 15

def run_batch(test_idxs, offline = False):
    global old_baseline
    baseline, old_baseline = [], [0] * len(test_idxs)
    n_decodes = 0
    n_cycles = 0
    decoding_time = 0
    import os
    if(os.path.exists("batch_test_baseline.pkl")):
        with open("batch_test_baseline.pkl","rb") as f:
            old_baseline = pickle.load(f)

    folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib/20m_busy/"

    for n in test_idxs:
        if(offline):
            print(f"\n============================\nRunning offline with test_{n:02d}")
            nd, dt = run_offline(f"{folder}/test_{n:02d}", '_offline_PyFT8.txt', [100,3100])
        else:
            print(f"\n============================\nRunning cycle_manager with test_{n:02d}")
            nd, dt = run(f"{folder}/test_{n:02d}", '_cyclemgr_PyFT8.txt',  [100,3100])
        baseline.append(nd)
        
        print(f"{nd} decodes ({nd - old_baseline[n_cycles]:+2d})")
        n_decodes += nd
        decoding_time += dt
        n_cycles += 1
        print(f"Avg decodes per cycle: {n_decodes / n_cycles : 4.1f}")
        print(f"Avg time per cycle: {decoding_time / n_cycles : 4.1f}")

    with open("batch_test_baseline_new.pkl","wb") as f:
        pickle.dump(baseline,f)

run_batch(range(1,39), offline = False)


