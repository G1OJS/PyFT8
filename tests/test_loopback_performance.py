import numpy as np
from PyFT8.ldpc import LdpcDecoder
from PyFT8.FT8_encoder import encode_bits77
from PyFT8.FT8_crc import bitsLE_to_int
import time

gray_seq = [0,1,3,2,5,6,4,7]
num_symbols = 79
tones_persymb = 8
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
costas=[3,1,4,0,6,5,2]
    
class Candidate:
    def __init__(self, t0_idx, dt, f0_idx, df):
        self.t0_idx = t0_idx
        self.f0_idx = f0_idx
        self.origin = (t0_idx, f0_idx, dt*t0_idx, df * (f0_idx + 1))
        self.size = (79*3, 8*3)
        self.n_its = 0
        self.ldpc = LdpcDecoder()

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


def single_loopback(snr=20, max_its = 10):
    f_base = 1000
    
   # input_int = int(2**77 * np.random.rand())
    input_int = 133398380429840941814865
    symbols, _, _, _, _ = encode_bits77(input_int)
    symbols_framed = [-10]*7
    symbols_framed.extend(symbols)
    symbols_framed.extend([-10]*7)
    audio_data = create_ft8_wave(symbols_framed, f_base = f_base, amplitude = 0.1, added_noise = -snr)

    dt = 0.16/3
    symbs_persec = 1/0.16
    sample_rate = 12000
    max_freq = 3000
    FFT_len = int(3 * 12000 // symbs_persec)
    FFT_out_len = int(FFT_len/2) + 1
    fmax_fft = sample_rate/2
    nFreqs = int(FFT_out_len * max_freq / fmax_fft)
    samps_perhop = int(12000 / (3*symbs_persec))
    fft_window = np.kaiser(FFT_len, 20)
    df = max_freq / (nFreqs)

    hops_percycle = 270
    fine_grid_complex = np.zeros((hops_percycle, nFreqs), dtype = np.complex64)
    for hop in range(hops_percycle):
        samp0 = hop*samps_perhop
        audio_for_fft = audio_data[samp0:samp0 + FFT_len]
        audio_for_fft = audio_for_fft * fft_window
        fine_grid_complex[hop,:] = np.fft.rfft(audio_for_fft)[:nFreqs]

    t0_idx=18
    f0_idx=int(f_base/df)
    c = Candidate(t0_idx, dt,  f0_idx, df)
    c.synced_grid_complex = fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0], c.origin[1]:c.origin[1]+c.size[1]]
    synced_grid_complex = c.synced_grid_complex.reshape(num_symbols, 3, tones_persymb, 3)
    synced_grid_pwr = np.abs(synced_grid_complex[:,0,:,1])**2
    p = synced_grid_pwr[payload_symb_idxs] 
    llr0 = np.log(np.max(p[:,[4,5,6,7]], axis=1)) - np.log(np.max(p[:,[0,1,2,3]], axis=1))
    llr1 = np.log(np.max(p[:,[2,3,4,7]], axis=1)) - np.log(np.max(p[:,[0,1,5,6]], axis=1))
    llr2 = np.log(np.max(p[:,[1,2,6,7]], axis=1)) - np.log(np.max(p[:,[0,3,4,5]], axis=1))
    c.llr = np.column_stack((llr0, llr1, llr2)).ravel()
    c.llr_sd = np.std(c.llr)
    c.llr = np.clip(3.5 * c.llr / c.llr_sd, -3.7, 3.7)
    c.llr = np.asarray(c.llr, dtype=np.float32)
    c.llr0 = c.llr.copy()
    
    t0 = time.time()
    for n_its in range(max_its):
        c.llr, c.ncheck = c.ldpc.do_ldpc_iteration(c.llr)
        if(n_its == 0): ncheck_initial = c.ncheck
        success = (c.ncheck == 0)
        if(success): break
    t_ldpc = time.time() - t0

    output_bits = (c.llr > 0).astype(int).tolist()[:77]
    output_int = bitsLE_to_int(output_bits)
    success = output_int == input_int
    results = {'snr':snr, 'success': success, 'llr_sd':c.llr_sd, 'sumabs_llr':np.sum(np.abs(c.llr0)), 'ncheck0':ncheck_initial, 'n_its':n_its,'t_ldpc':t_ldpc}
    
    return results

def test_vs_snr(snrs, max_its = 20, load_last = False):
    import matplotlib.pyplot as plt
    import pickle
    if(load_last):
        with open("last_montecarlo.pkl", "rb") as f:
            successes, failures = pickle.load(f)
    else:    
        successes, failures = [],[]
        for i, snr in enumerate(snrs):
            results = single_loopback(snr = snr, max_its = max_its)
            if(results['success']):
                successes.append(results)
            else:
                failures.append(results)
            if(not (i % 10)):
                print(f"{i}/{len(snrs)}")
        with open("last_montecarlo.pkl", "wb") as f:
            pickle.dump((successes, failures),f)        


    plot_params = ['llr_sd', 'sumabs_llr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = 'green')
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = 'red')
        axs[iax].set_ylabel(param)
        axs[iax].set_xlabel("Imposed channel SNR")
    plt.suptitle("Proxies vs imposed SNR for successes and failures")
    plt.tight_layout()
    plt.show()

    plot_params = ['snr', 'llr_sd', 'sumabs_llr', 'ncheck0']
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
        axs[iax].set_ylabel("Decoder success")

    plt.suptitle("Decoder performance against imposed SNR and proxies")
    plt.tight_layout()
    plt.show()


snrs = -26 + 10 * np.random.random(500)
test_vs_snr(snrs)
#test_vs_snr(snrs, load_last = True)



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
