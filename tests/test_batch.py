import numpy as np
import time
import pickle
import threading
from PyFT8.receiver import receiver, AudioIn, Waterfall
from PyFT8.params import params

data_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/data/ft8_lib_20m_busy"
results_folder = "C:/Users/drala/Documents/Projects/GitHub/PyFT8/tests/results/ft8_lib_20m_busy"

def on_decode(dd):
    global decodes
    decodes.append(dd)

def get_textfile_line_count(filepath):
    with open(filepath, 'r') as f:
        l = f.readlines()
    return len(l)

def process_wav(dataset):
    global decodes
    nu, n_decodes = 0, 0
    decodes = []
    textfile_rows = []

    audio_in.dBgrid_main_ptr = 0
    audio_data = audio_in.load_wav(dataset + ".wav")
    time.sleep(5)
    
    for dd in decodes:
        n_decodes +=1
        row = f"000000 {dd['snr']:3d} {dd['dt']:3.1f} {dd['f']:4d} ~ {dd['msg']:<23} {dd['sync_idx']} {dd['decode_path']}"
        textfile_rows.append(row)

    with open(dataset + '.txt', "w") as f:
        for r in textfile_rows:
            f.write(f"{r}\n")

    return n_decodes, 15, nu

def run_batch(waterfall):

    threading.Thread(target = receiver, args =(audio_in, [200, 3100], on_decode, waterfall,), daemon=True ).start()

    test_idxs = range(1, 39)
    baseline, old_baseline = [], [{'n_decodes':0, 'processing_time':0, 'n_unfinished':0}] * len(test_idxs)
    n_decodes = 0
    n_decodes_wsjtx = 0
    n_decodes_ft8_lib = 0
    n_cycles = 0
    processing_time = 0
    n_unfinished = 0
    summary_rows = []

    import os
    if(os.path.exists("baseline.pkl")):
        with open("baseline.pkl","rb") as f:
            old_baseline = pickle.load(f)
    
    for n in test_idxs:
        nd, pt, nu = process_wav(f"{data_folder}/test_{n:02d}")
        print("Test complete")
        baseline.append({'n_decodes':nd, 'processing_time':pt, 'n_unfinished':nu})
        n_decodes_wsjtx += get_textfile_line_count(f"{results_folder}/test_{n:02d}_wsjtx_2.7.0_NORM.txt")
        n_decodes_ft8_lib += get_textfile_line_count(f"{results_folder}/test_{n:02d}_ft8_lib.txt")

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

    with open("baseline_new.pkl","wb") as f:
        pickle.dump(baseline,f)

    with open("summary.txt", "w") as f:
        for i, r in enumerate(summary_rows):
            row = f" {r}"
            print(row)
            f.write(f"{row}\n")

def run_test(waterfall):
    threading.Thread(target = run_batch, args = (waterfall,)).start()

audio_in = AudioIn(None, 3100)
waterfall = Waterfall(audio_in.dBgrid_main, params['HPS'], params['BPT'], run_test, lambda msg: print(msg))



