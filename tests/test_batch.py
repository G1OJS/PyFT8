
import numpy as np
from PyFT8.spectrum import Spectrum
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
from PyFT8.time_utils import global_time_utils
import time
import pickle

global old_baseline

def get_textfile_line_count(filepath):
    with open(filepath, 'r') as f:
        l = f.readlines()
    return len(l)

def run_offline(dataset, output_stub, freq_range):
    spectrum = Spectrum(FT8, 12000, 3100, 4, 2)
    spectrum.audio_in.load_wav(dataset+".wav")
    f0_idxs = range(int(freq_range[0]/spectrum.df),
                        min(spectrum.nFreqs - spectrum.fbins_per_signal, int(freq_range[1]/spectrum.df)))
    textfile_rows = []
    msgs = []
    candidates = spectrum.search(f0_idxs, '000000_000000')
    
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
            textfile_rows.append(row)
            n_decodes +=1
    processing_time = time.time()-t0

    with open(dataset + output_stub, "w") as f:
        for r in textfile_rows:
            f.write(f"{r}\n")

    return n_decodes, processing_time, 0

def run_cycle_manager(dataset, output_stub, freq_range):
    nu, n_decodes = 0, 0
    decodes = []
    textfile_rows = []
    
    def on_decode(dd):
        nonlocal decodes
        decodes.append(dd)

    def on_finished(fd):
        nonlocal nu
        nu = fd['n_unfinished']

    cycle_manager = Cycle_manager(FT8, on_decode, wav_input = dataset+".wav", on_finished = on_finished, verbose = False)

    while not cycle_manager.spectrum.audio_in.wav_finished:
        time.sleep(0.5)

    for dd in decodes:
        n_decodes +=1
        row = f"000000 {dd['snr']:3d} {dd['dt']:3.1f} {dd['f']:4d} ~ {dd['msg']:<23} {dd['sync_idx']} {dd['decode_path']}"
        textfile_rows.append(row)

    
    with open(dataset + output_stub, "w") as f:
        for r in textfile_rows:
            f.write(f"{r}\n")

    return n_decodes, 15, nu

def run_batch(test_idxs, offline = False):
    global old_baseline
    baseline, old_baseline = [], [{'n_decodes':0, 'processing_time':0, 'n_unfinished':0}] * len(test_idxs)
    n_decodes = 0
    n_decodes_wsjtx = 0
    n_decodes_ft8_lib = 0
    n_cycles = 0
    processing_time = 0
    n_unfinished = 0
    summary_rows = []
    import os

    output_file_stub = "batch_test_offline" if(offline) else "batch_test_cycle_manager"
    
    if(os.path.exists(output_file_stub+"_baseline.pkl")):
        with open(output_file_stub+"_baseline.pkl","rb") as f:
            old_baseline = pickle.load(f)

    folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib/20m_busy/"

    for n in test_idxs:
        if(offline):
            nd, pt, nu = run_offline(f"{folder}/test_{n:02d}", '_offline_PyFT8.txt', [100,3100])
        else:
            nd, pt, nu = run_cycle_manager(f"{folder}/test_{n:02d}", '_cyclemgr_PyFT8.txt',  [100,3100])
        baseline.append({'n_decodes':nd, 'processing_time':pt, 'n_unfinished':nu})
        n_decodes_wsjtx += get_textfile_line_count(f"{folder}/test_{n:02d}_wsjtx_2.7.0_NORM.txt")
        n_decodes_ft8_lib += get_textfile_line_count(f"{folder}/test_{n:02d}_ft8_lib.txt")

        cycle_row = f"Test_{n:02d}.wav {nd} decodes ({nd - old_baseline[n_cycles]['n_decodes']:+2d}) {pt:4.2f} seconds"
        cycle_row = cycle_row + f" ({pt - old_baseline[n_cycles]['processing_time']:+4.2f}), {nu} ({nu - old_baseline[n_cycles]['n_unfinished']:+d}) unfinished"
        print("")
        print(cycle_row)
        summary_rows.append(cycle_row)

        n_cycles += 1
        n_decodes += nd
        processing_time += pt
        n_unfinished += nu
        cumulative_row = f"Totals: {n_decodes} decodes, {n_decodes / n_cycles : 4.1f} decodes/cycle, {processing_time / n_cycles : 4.1f} s/cycle,"
        cumulative_row = cumulative_row + f"{n_decodes / n_decodes_wsjtx : 4.1%} wsjtx, {n_decodes / n_decodes_ft8_lib : 4.1%} ft8_lib,"
        cumulative_row = cumulative_row + f" {processing_time:4.2f} decoding seconds, {n_unfinished} unfinished "
        print(cumulative_row)

    summary_rows.append(cumulative_row)

    with open(output_file_stub + "_baseline_new.pkl","wb") as f:
        pickle.dump(baseline,f)

    with open(output_file_stub+"_summary.txt", "w") as f:
        for i, r in enumerate(summary_rows):
            row = f" {r}"
            print(row)
            f.write(f"{row}\n")
    

run_batch(range(1,39), offline = True)
#run_batch(range(1,39), offline = False)


