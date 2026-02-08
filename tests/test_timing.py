
import numpy as np
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
from PyFT8.time_utils import global_time_utils
import time


def tab_print(dd):
    row = f"{dd['decoder']}, {dd['cs']} {dd['f']:4d} {dd['snr']:+04d} {dd['dt']:4.1f} {dd['td']:<4} {dd['msg']:<23} "
    global_time_utils.tlog(f"{row}")    


def run(dataset, freq_range):
    decodes = []
    results = []
    
    def on_decode(dd):
        tab_print(dd)
        decodes.append(dd)
        row = f"000000 {dd['snr']:3d} {dd['dt']:3.1f} {dd['f']:4d} ~ {dd['msg']}"
        results.append(row)

    cycle_manager = Cycle_manager(FT8, on_decode, wav_input = dataset+".wav", verbose = True)
    t0 = time.time()

    while not cycle_manager.spectrum.audio_in.wav_finished:
        time.sleep(0.5)
    n_decodes = len(decodes)
    print(f"{n_decodes} decodes")
    
    with open(dataset + output_stub, "w") as f:
        for r in results:
            f.write(f"{r}\n")

    return n_decodes

def run_batch():
    n_decodes = 0
    n_cycles = 0
    for n in range(1,39):
        print(f"\n============================\nRunning test with test_{n:02d}")
        nd = run(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy\test_"+f"{n:02d}", [100,3100])
        n_decodes += nd
        n_cycles += 1   
        print(f"Avg decodes per cycle: {n_decodes / n_cycles : 4.1f}")

output_stub = '_cyclemgr_PyFT8.txt'
input_file = r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy\test_01.wav"

run_batch()


