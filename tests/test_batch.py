
import numpy as np
from PyFT8.sigspecs import FT8
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.spectrum import Spectrum
from PyFT8.ldpc import LdpcDecoder
from PyFT8.osd import osd_decode_minimal
import time

def run(dataset, freq_range):
    spectrum = Spectrum(FT8, 12000, 3100, 3, 3)
    spectrum.audio_in.load_wav(dataset+".wav")
    f0_idxs = range(int(freq_range[0]/spectrum.df),
                        min(spectrum.nFreqs - spectrum.fbins_per_signal, int(freq_range[1]/spectrum.df)))

    results = []
    msgs = []
    candidates = spectrum.search(f0_idxs, '000000_000000')

    t0 = time.time()
    for c in candidates:
        c.demap(spectrum)
    candidates.sort(key = lambda c: -c.llr0_sd)
    for c in candidates:
        c.decode()
        if(c.msg and not c.msg in msgs):
            msgs.append(c.msg)
            row = f"000000 {c.snr:3d} {c.dt:3.1f} {c.fHz:4d} ~ {' '.join(c.msg)}"
            print(f"{time.time()-t0:5.2f} {c.sync_score:4.1f} {c.llr0_sd:4.1f} {c.ncheck0:2d} {row:<45} {c.decode_path}")
            results.append(row)
    
    with open(dataset+"_tmp_pyft8.txt", "w") as f:
        f.write('\n'.join(results))
 

for n in range(1,39):
    print(f"Running test with test_{n:02d}")
    run(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy\test_"+f"{n:02d}", [100,3100])

#run(r"C:\Users\drala\Documents\Projects\ft8_lib test\test\wav\20m_busy\test_01", [100,3100])

#run("data/G4WNT/FT-8-Comp-31-12-22-5mins-2-12000", [100,3100])
#run("data/210703_133430", [100,3100])
#run(None, [100,3100])

#plot_success_file('compare_data.pkl')





