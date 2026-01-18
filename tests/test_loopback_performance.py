import numpy as np
from PyFT8.cycle_manager import Cycle_manager, Candidate
from PyFT8.sigspecs import FT8
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.ldpc import LdpcDecoder
from PyFT8.FT8_encoder import encode_bits77, pack_message
from PyFT8.FT8_crc import bitsLE_to_int
import time

global test_messages
test_messages = []


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

def generate_test_messages():
    global test_messages
    messages = ['CQ G1OJS IO90', 'G1OJS W3PEN -13', 'W3PEN G1OJS RR73', 'G1OJS W3PEN 73']
    for msg in messages:
        c1, c2, grid_rpt = msg.split()
        symbols = pack_message(c1, c2, grid_rpt)
        test_messages.append((msg, symbols))


def single_loopback(snr=20):
    t0 = time.time()
    f_base = 250

    imsg = np.random.randint(0, len(test_messages))
    input_msg, symbols = test_messages[imsg]
    symbols_framed = [-10]*7
    symbols_framed.extend(symbols)
    symbols_framed.extend([-10]*7)
    audio_data = create_ft8_wave(symbols_framed, f_base = f_base, amplitude = 0.1, added_noise = -snr)
    t_gen = time.time()   
    
    z = cycle_manager.spectrum.audio_in.zgrid_main
    win = np.kaiser(fft_len, 20)
    for hop in range(hops_percycle):
        samp0 = hop*samps_perhop
        audio_for_fft = audio_data[samp0:samp0 + fft_len]
        if(len(audio_for_fft) == fft_len):
            audio_for_fft = audio_for_fft * win
            z[hop,:nFreqs] = np.fft.rfft(audio_for_fft)[:nFreqs]
    cycle_manager.spectrum.audio_in.pgrid_main = z.real*z.real + z.imag*z.imag

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
    output_msg = FT8_unpack(output_bits)
    output_msg = ' '.join(output_msg)

    t_decode = time.time()

    success = output_msg == input_msg
    results = {'snr':snr, 'success': success, 'llr_sd':c.llr0_sd, 'sumabs_llr':np.sum(np.abs(c.llr0)),
               'ncheck0':c.ncheck0, 'n_its':c.counters[1], 'decode_path':c.decode_path, 
               't_gen':1000*(t_gen-t0), 't_spec':1000*(t_spec-t_gen), 't_demap':1000*(t_demap-t_spec), 't_decode':1000*(t_decode-t_demap)}
    
    return results

def test_vs_snr(run_params = "Default", ntrials = 200, snr_range = [-26,-16]):
    generate_test_messages()
    snrs = snr_range[0] + (snr_range[1] - snr_range[0]) * np.random.random(ntrials)
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
    with open(f"results/data/montecarlo_{run_params}.pkl", "wb") as f:
        pickle.dump((successes, failures),f)

import pickle
import matplotlib.pyplot as plt
import matplotlib.lines as lines

CAT_COLOURS = ['red','lime','blue','orange','green']
global leg_decode_type, leg_decode_outcome

def decode_category(dpath):
    if(not "#" in dpath):
        return 0
    if(dpath[3]=="#" or dpath[7]=="#" ):
        return 1
    elif('O' in dpath):
        return 2
    elif('A' in dpath):
        return 3
    elif('L' in dpath):
        return 4

def make_legends():
    global leg_decode_type, leg_decode_outcome
    leg_decode_type = [ lines.Line2D([0], [0], marker='o', color='w',label='Immediate', markerfacecolor=CAT_COLOURS[1], markersize=8),
                        lines.Line2D([0], [0], marker='o', color='w',label='LDPC', markerfacecolor=CAT_COLOURS[4], markersize=8),
                        lines.Line2D([0], [0], marker='o', color='w',label='LDPC + bitflips', markerfacecolor=CAT_COLOURS[3], markersize=8),
                        lines.Line2D([0], [0], marker='o', color='w',label='OSD', markerfacecolor=CAT_COLOURS[2], markersize=8),
                        lines.Line2D([0], [0], marker='o', color='w',label='Timeout not tested', markerfacecolor=CAT_COLOURS[0], markersize=8),
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
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = s_colors)
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = f_colors, edgecolor = 'red', lw=1.5, zorder=3)
        axs[iax].set_ylabel(f"{param}, ms")
        axs[iax].set_xlabel(f"Imposed channel SNR")
        add_legends(axs[iax])
    plt.suptitle(f"Cycle timings vs imposed channel SNR for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    fig.savefig(f"results/test_timings_{run_params}.png", bbox_inches="tight")

    plot_params = ['llr_sd', 'sumabs_llr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = s_colors)
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = f_colors,  edgecolor = 'red', lw=1.5, zorder=3)
        axs[iax].set_ylabel(param)
        axs[iax].set_xlabel("Imposed channel SNR")
        add_legends(axs[iax])
    plt.suptitle(f"Proxies vs imposed SNR for successes and failures for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    fig.savefig(f"results/proxy_plots_{run_params}.png", bbox_inches="tight")

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

    plt.suptitle(f"Decoder performance against imposed SNR and proxies for {run_params} n_trials = {n_trials}")
    plt.tight_layout()
    fig.savefig(f"results/decoder_performance_{run_params}.png", bbox_inches="tight")


run_params = "full_decoder_osd_50"
test_vs_snr(run_params, ntrials = 2000)
plot_results(run_params)

