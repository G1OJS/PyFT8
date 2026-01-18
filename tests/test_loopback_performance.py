import numpy as np
from PyFT8.cycle_manager import Cycle_manager, Candidate
from PyFT8.sigspecs import FT8
from PyFT8.ldpc import LdpcDecoder
from PyFT8.FT8_encoder import encode_bits77
from PyFT8.FT8_crc import bitsLE_to_int
import time

gray_seq = [0,1,3,2,5,6,4,7]
num_symbols = 79
tones_persymb = 8
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
costas=[3,1,4,0,6,5,2]


def onDecode(c):
    pass
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, verbose = False, freq_range = [100,500])
cycle_manager.running = False

hops_percycle = cycle_manager.spectrum.audio_in.hops_percycle
samps_perhop = int(cycle_manager.spectrum.audio_in.sample_rate // cycle_manager.spectrum.audio_in.hop_rate)
fft_len = cycle_manager.spectrum.audio_in.fft_len
nFreqs = cycle_manager.spectrum.audio_in.nFreqs
df = cycle_manager.spectrum.df
dt = cycle_manager.spectrum.dt
    
def create_ft8_wave(symbols, fs=12000, f_base=873.0, f_step=6.25, amplitude = 0.5, added_noise = -50):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    phase = 0
    waveform = []
    for s in symbols:
        f = f_base + s * f_step
        phase_inc = 2 * np.pi * f / fs
        w = np.sin(phase + phase_inc * np.arange(symbol_len))
        waveform.append(w)
        phase = (phase + phase_inc * symbol_len) % (2 * np.pi)
    waveform = np.concatenate(waveform).astype(np.float32)
    waveform = waveform.astype(np.float32)
    waveform = amplitude * waveform / np.max(np.abs(waveform))
    if(added_noise > -50):
        noise = np.random.randn(len(waveform))
        signal_rms = np.sqrt(np.mean(waveform**2))
        noise_rms = signal_rms * 10**(added_noise / 20)
        noise *= noise_rms / np.sqrt(np.mean(noise**2))
        waveform_noisy = waveform + noise
    return waveform_noisy

def single_loopback(snr=20):
    t0 = time.time()
    f_base = 250

   # input_int = int(2**77 * np.random.rand())
    input_int = 133398380429840941814865
    symbols, _, _, _, _ = encode_bits77(input_int)
    symbols_framed = [-10]*7
    symbols_framed.extend(symbols)
    symbols_framed.extend([-10]*7)
    audio_data = create_ft8_wave(symbols_framed, f_base = f_base, amplitude = 0.1, added_noise = -snr)

    t_gen = time.time()   
    
    fine_grid_complex = cycle_manager.spectrum.audio_in.zgrid_main
    for hop in range(hops_percycle):
        samp0 = hop*samps_perhop
        audio_for_fft = audio_data[samp0:samp0 + fft_len]
        if(len(audio_for_fft) == fft_len):
            audio_for_fft = audio_for_fft * np.kaiser(fft_len,20)
            fine_grid_complex[hop,:nFreqs] = np.fft.rfft(audio_for_fft)[:nFreqs]
    cycle_manager.spectrum.audio_in.pgrid_main = np.abs(cycle_manager.spectrum.audio_in.zgrid_main)**2

    t_spec = time.time()

    t0_idx=18
    f0_idx=int(f_base/df)
    cands = cycle_manager.spectrum.search([f0_idx],"000000_000000")
    c = cands[0]
    c.demap(cycle_manager.spectrum)

    t_demap = time.time()
    
    for its in range(20):
        c.progress_decode()
        if("#" in c.decode_path):
            break

    output_bits = (c.llr > 0).astype(int).tolist()[:77]
    output_int = bitsLE_to_int(output_bits)

    t_decode = time.time()

    success = output_int == input_int
    results = {'snr':snr, 'success': success, 'llr_sd':c.llr0_sd, 'sumabs_llr':np.sum(np.abs(c.llr0)),
               'ncheck0':c.ncheck0, 'n_its':c.counters[1],
               't_gen':1000*(t_gen-t0), 't_spec':1000*(t_spec-t_gen), 't_demap':1000*(t_demap-t_spec), 't_decode':1000*(t_decode-t_demap)}
    
    return results

def test_vs_snr(snrs, load_last = False):
    import pickle
    successes, failures = [],[]
    for i, snr in enumerate(snrs):
        results = single_loopback(snr = snr)
        if(results['success']):
            successes.append(results)
        else:
            failures.append(results)
        if(not (i % 10)):
            print(f"{i}/{len(snrs)}")
    with open("last_montecarlo.pkl", "wb") as f:
        pickle.dump((successes, failures),f)
    plot_results()

def plot_results(filename = 'last_montecarlo.pkl'):
    import pickle
    import matplotlib.pyplot as plt
    with open(filename, "rb") as f:
        successes, failures = pickle.load(f)

    plot_params = ['t_gen', 't_demap', 't_decode']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = 'green')
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = 'red')
        axs[iax].set_ylabel(f"{param}, ms")
        axs[iax].set_xlabel("Cycle timings vs imposed channel SNR")
    plt.suptitle(f"")
    plt.tight_layout()
    plt.show()

    plot_params = ['llr_sd', 'sumabs_llr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = 'green')
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = 'red')
        axs[iax].set_ylabel(param)
        axs[iax].set_xlabel("Imposed channel SNR")
    plt.suptitle(f"Proxies vs imposed SNR for successes and failures for {filename}")
    plt.tight_layout()
    plt.show()

    plot_params = ['snr', 'llr_sd', 'sumabs_llr', 'ncheck0']
    plot_ranges = [[-26,-19],[0,1.5],[350,550],[0,45]]
    
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):        
        xs = [s[param] for s in successes]
        xf = [f[param] for f in failures]
        x0 = np.min(xs)
        xn = np.max(xs)
        
        nbins = 30
        dx = (xn-x0)/(nbins -1)
        histvals = []
        xbins = np.arange(x0, xn, dx)
        for xbin in xbins:
            tot, suc = 0, 0
            for x in [x for x in xs if xbin <= x < xbin+dx]:
                tot +=1
                suc +=1
            for x in [x for x in xf if xbin <= x < xbin+dx]:
                tot +=1
            histvals.append(suc/tot if tot>0 else 0)
                
        p = axs[iax].plot(xbins,histvals, alpha = 0.7, lw=1)  
        axs[iax].set_xlabel(param)
        axs[iax].set_xlim(plot_ranges[iax])
        axs[iax].set_ylabel("Decoder success")

    plt.suptitle(f"Decoder performance against imposed SNR and proxies for {filename}")
    plt.tight_layout()
    plt.show()

snrs = -26 + 10 * np.random.random(100)

test_vs_snr(snrs)
#plot_results(filename = "data/montecarlo_ldpc_only.pkl")



"""
-24.00 dB   12.0% avg_its = 18     ms per ldpc =  3.58   ms_per_iteration = 0.20   
-23.50 dB   38.0% avg_its = 14     ms per ldpc =  2.88   ms_per_iteration = 0.21   
-23.00 dB   68.0% avg_its = 10     ms per ldpc =  2.04   ms_per_iteration = 0.21   
-22.50 dB   86.0% avg_its = 6      ms per ldpc =  1.30   ms_per_iteration = 0.22   
-22.00 dB   98.0% avg_its = 2      ms per ldpc =  0.72   ms_per_iteration = 0.35   
-21.50 dB  100.0% avg_its = 1      ms per ldpc =  0.38   ms_per_iteration = 0.37  
"""


"""
import matplotlib.pyplot as plt
fig,ax = plt.subplots()

for max_ncheck in [26,27,28,29,30,31,32,33,34]:
    res, x = test_vs_snr()
    ax.plot(x, res, label = f"{max_ncheck}")
    ax.set_title("Success vs max_ncheck")
    ax.legend()
    plt.pause(0.5)

plt.show()
"""
