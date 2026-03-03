import numpy as np
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.candidate import Candidate, params
from PyFT8.spectrum import Spectrum
from PyFT8.sigspecs import FT8
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.ldpc import LdpcDecoder
from PyFT8.FT8_encoder import encode_bits77, pack_message
from PyFT8.FT8_crc import bitsLE_to_int
import time

global test_messages
test_messages = []

params.update({'MIN_LLR_SD': 0})

gray_seq = [0,1,3,2,5,6,4,7]
num_symbols = 79
tones_persymb = 8
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
costas=[3,1,4,0,6,5,2]

def onDecode(c):
    pass
cycle_manager = Cycle_manager(FT8, on_decode = False, run = False, verbose = False, freq_range = [100,500])

hops_percycle = cycle_manager.spectrum.audio_in.hops_percycle
samps_perhop = cycle_manager.spectrum.audio_in.samples_perhop
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

def generate_test_messages():
    global test_messages
    messages = ['CQ G1OJS IO90', 'G1OJS W3PEN -13', 'W3PEN G1OJS RR73', 'G1OJS W3PEN 73']
    for msg in messages:
        c1, c2, grid_rpt = msg.split()
        symbols = pack_message(c1, c2, grid_rpt)
        test_messages.append((msg, symbols))


def single_loopback(imposed_snr=20, amplitude = 0.5):
    t0 = time.time()
    f_base = 250

    imsg = np.random.randint(0, len(test_messages))
    input_msg, symbols = test_messages[imsg]
    symbols_framed = [-10]*7
    symbols_framed.extend(symbols)
    symbols_framed.extend([-10]*7)
    audio_data = create_ft8_wave(symbols_framed, f_base = f_base, amplitude = amplitude, added_noise = -imposed_snr)
    t_gen = time.time()   
    
    z = np.zeros_like(cycle_manager.spectrum.audio_in.dB_main, dtype = np.complex64)
    win = cycle_manager.spectrum.audio_in.fft_window
    for hop in range(hops_percycle):
        samp0 = hop*samps_perhop
        audio_for_fft = audio_data[samp0:samp0 + fft_len]
        if(len(audio_for_fft) == fft_len):
            audio_for_fft = audio_for_fft * win
            z[hop,:nFreqs] = np.fft.rfft(audio_for_fft)[:nFreqs]
    cycle_manager.spectrum.audio_in.dB_main = 10*np.log10(z.real*z.real + z.imag*z.imag + 1e-12)

    t_spec = time.time()

    t0_idx=3
    f0_idx=int(f_base/df)
    cands = cycle_manager.spectrum.search([f0_idx],"000000_000000", 0)
    cands = cands + cycle_manager.spectrum.search([f0_idx],"000000_000000", 1)
    c = cands[0]
    c.demap(cycle_manager.spectrum)
    t_demap = time.time()
    c.decode()
    output_msg = ' '.join(c.msg)

    t_decode = time.time()

    success = output_msg == input_msg
    results = c.decode_dict
    results.update({'imposed_snr':imposed_snr, 'success': success,  
               't_gen':1000.0*(t_gen-t0), 't_spec':1000.0*(t_spec-t_gen), 't_demap':1000.0*(t_demap-t_spec), 't_decode':1000.0*(t_decode-t_demap)})
    
    return results

def test_vs_imposed_snr(run_params = "Default", ntrials = 200, imposed_snr_range = [-26,-16]):
    generate_test_messages()
    amplitudes = np.random.random(ntrials)
    imposed_snrs = imposed_snr_range[0] + (imposed_snr_range[1] - imposed_snr_range[0]) * np.random.random(ntrials)
    import pickle
    successes, failures = [],[]
    for i, imposed_snr in enumerate(imposed_snrs):
        amp = amplitudes[i]
        results = single_loopback(imposed_snr = imposed_snr, amplitude = amp)
        if(results['success']):
            successes.append(results)
        else:
            failures.append(results)
        if(not (i % 10)):
            print(f"{i}/{len(imposed_snrs)}")
    with open(f"results/data/montecarlo_{run_params}.pkl", "wb") as f:
        pickle.dump((successes, failures),f)

import pickle
import matplotlib.pyplot as plt
import matplotlib.lines as lines

CAT_COLOURS = ['lime','green']
global leg_decode_type, leg_decode_outcome

def savefig(fig, savename):
    print(f"Results saved to {savename}")
    fig.savefig(savename, bbox_inches="tight")

def decode_category(dpath):
    if('L' in dpath):
        return 1
    else:
        return 0

def make_legends():
    global leg_decode_type, leg_decode_outcome
    leg_decode_type = [ lines.Line2D([0], [0], marker='o', color='w',label='Immediate', markerfacecolor=CAT_COLOURS[0], markersize=8),
                        lines.Line2D([0], [0], marker='o', color='w',label='LDPC', markerfacecolor=CAT_COLOURS[1], markersize=8),
                        ]

    leg_decode_outcome = [lines.Line2D([0], [0], marker='o', color='k',label='Success', markersize=8),
                          lines.Line2D([0], [0], marker='o', markeredgecolor='red', markeredgewidth=2.0, color='k',label='Failure', markersize=8),
                        ]


def add_legends(ax):
    leg1 = ax.legend(handles=leg_decode_type, loc='upper left')
    ax.add_artist(leg1) 
    ax.legend(handles=leg_decode_outcome, loc='upper right')

def plot_results(run_params = "Default"):
    with open(f"results/data/montecarlo_{run_params}.pkl", "rb") as f:
        successes, failures = pickle.load(f)
    n_trials = len(successes)+len(failures)

    make_legends()
    s_colors = [CAT_COLOURS[decode_category(s['decode_path'])] for s in successes]
    f_colors = [CAT_COLOURS[decode_category(f['decode_path'])] for f in failures]
    
    plot_params = ['t_gen', 't_spec', 't_demap', 't_decode']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['imposed_snr'] for d in successes],[d[param] for d in successes], color = s_colors)
        axs[iax].scatter([d['imposed_snr'] for d in failures],[d[param] for d in failures], color = f_colors, edgecolor = 'red', lw=1.5, zorder=3)
        axs[iax].set_ylabel(f"{param}, ms")
        axs[iax].set_xlabel(f"Imposed channel snr")
        add_legends(axs[iax])
    plt.suptitle(f"Cycle timings vs imposed channel imposed_snr for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    savefig(fig, f"results/test_timings_{run_params}.png")

    plot_params = ['llr_sd', 'snr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['imposed_snr'] for d in successes],[d[param] for d in successes], color = s_colors)
        axs[iax].scatter([d['imposed_snr'] for d in failures],[d[param] for d in failures], color = f_colors,  edgecolor = 'red', lw=1.5, zorder=3)
        axs[iax].set_ylabel(param)
        axs[iax].set_xlabel("Imposed channel snr")
        add_legends(axs[iax])
    plt.suptitle(f"Proxies vs imposed imposed_snr for successes and failures for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    savefig(fig, f"results/proxy_plots_{run_params}.png")

    plot_params = ['llr_sd', 'imposed_snr', 'ncheck0']
    plot_ranges = [[0.25,0.75], [-26,-16],[0,55]]
    
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

    plt.suptitle(f"Decoder performance against imposed imposed_snr and proxies for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    savefig(fig, f"results/decoder_performance_{run_params}.png")
 

run_params = "default"
test_vs_imposed_snr(run_params, ntrials = 200)
plot_results(run_params)

