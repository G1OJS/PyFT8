
import numpy as np
from PyFT8.sigspecs import FT8
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.spectrum import Spectrum
from PyFT8.ldpc import LdpcDecoder
from PyFT8.candidate import params
import time

def run(dataset, freq_range):
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

def run_batch():
    n_decodes = 0
    n_cycles = 0
    decoding_time = 0
    t0 = time.time()
    for n in range(1,39):
        print(f"\n============================\nRunning test with test_{n:02d}")
        nd, dt = run(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy\test_"+f"{n:02d}", [100,3100])
        n_decodes += nd
        decoding_time += dt
        n_cycles += 1   
        print(f"Avg decodes per cycle: {n_decodes / n_cycles : 4.1f}")
        print(f"Avg time per cycle: {decoding_time / n_cycles : 4.1f}")

output_stub = "_tmp_pyft8.txt"
run_batch()
print("With params:")
print(params)

#run(r"C:\Users\drala\Documents\Projects\ft8_lib test\test\wav\20m_busy\test_01", [100,3100])

#run("data/G4WNT/FT-8-Comp-31-12-22-5mins-2-12000", [100,3100])

#output_stub = "210703_133430"
#run("data/210703_133430", [100,3100])
#run(None, [100,3100])

#plot_success_file('compare_data.pkl')





