import numpy as np
import wave
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.ldpc import LdpcDecoder

SAMPLE_RATE = 12000
KAISER_IND = 6
OSAMP_FREQ = 3
WAV_FILE = "data/210703_133430.wav"
HOPS_PERCYCLE = int(15 / 0.16)


global zgrid_main, pgrid_main
pgrid_main = None
zgrid_main = None

def decode(llr):
    llr0 = llr.copy()
    ldpc = LdpcDecoder()
    ncheck = ldpc.calc_ncheck(llr)
    n_its = 0
    if(ncheck > 0):
        for n_its in range(1, 10):
            llr, ncheck = ldpc.do_ldpc_iteration(llr)
            if(ncheck == 0):break
    msg = "FAILED"
    n_err = "?"
    if(ncheck == 0):
        cw_bits = (llr > 0).astype(int).tolist()
        msg = FT8_unpack(cw_bits)
        n_err = np.count_nonzero(np.sign(llr) != np.sign(llr0))
        if(msg):
            msg = ' '.join(msg)
    return msg, n_its, n_err

def read_wav(wav_path):
    max_samples = 30 * SAMPLE_RATE
    wf = wave.open(wav_path, "rb")
    ptr = 0
    frames = True
    audio_samples = np.zeros((max_samples), dtype = np.float32)
    samples_per_frame = SAMPLE_RATE # convenience = 1 second frames
    while frames:
        frames = wf.readframes(samples_per_frame)
        if(frames):
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            ns = len(samples)
            audio_samples[ptr:ptr+ns] = samples
            ptr += ns
    print(f"Loaded {ptr} samples ({ptr/SAMPLE_RATE:5.2f}s)")
    return audio_samples

def get_spectrum(audio_samples, time_offset, phase_global, phase_per_symbol, max_freq = 3100, nSyms = 79):
    global zgrid_main, pgrid_main, fft_len, fft_window, nFreqs
    samples_per_symbol = int(SAMPLE_RATE  / 6.25 )
    fft_len = OSAMP_FREQ * samples_per_symbol
    fft_window=np.kaiser(fft_len, KAISER_IND)
    fft_df = SAMPLE_RATE / fft_len 
    nFreqs = int(max_freq / fft_df)
    samples_offset = int(time_offset * SAMPLE_RATE)
    pgrid_main = np.zeros((HOPS_PERCYCLE, nFreqs), dtype = np.float32)
    zgrid_main = np.zeros((HOPS_PERCYCLE, nFreqs), dtype = np.complex64)
    for sym_idx in range(nSyms):
        phs = np.pi*np.linspace(0, phase_global + sym_idx * phase_per_symbol, fft_len)
        za = np.zeros_like(fft_window, dtype = np.complex64)
        aud = audio_samples[samples_offset + sym_idx * samples_per_symbol: samples_offset + sym_idx * samples_per_symbol + fft_len]
        za[:len(aud)] = aud
        za = za * fft_window * np.exp(1j * phs)
        zgrid_main[sym_idx, :] = np.fft.fft(za)[:nFreqs]
        z = zgrid_main[sym_idx, :]
        pgrid_main[sym_idx, :] = z.real*z.real + z.imag*z.imag


def create_symbols(msg):
    msg = msg.split(" ")
    c28a, p1a = pack_ft8_c28(msg[0]) 
    c28b, p1b = pack_ft8_c28(msg[1])
    g15, ir = pack_ft8_g15(msg[2])
    i3 = 1
    n3 = 0
    bits77 = (c28a<<28+1+2+15+3) | (c28b<<2+15+3)|(0<<15+3)|(g15<< 3)|(i3)
    symbols, bits174_int, bits91_int, bits14_int, bits83_int = encode_bits77(bits77)
    return symbols

def calc_dB(pwr, dBrange = 20, rel_to_max = False):
    thresh = np.max(pwr) * 10**(-dBrange/10)
    pwr = np.clip(pwr, thresh, None)
    dB = 10*np.log10(pwr)
    if(rel_to_max):
        dB = dB - np.max(dB)
    return dB

def get_llr(p):
    p = calc_dB(p, dBrange = 30)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    llr = 3.8*llr/np.std(llr)
    return llr.flatten()

def show_spectrum(fig, ax, dBrange = 60):
    dB = calc_dB(pgrid_main, dBrange = dBrange, rel_to_max = True)
    im = ax.imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)


def show_sig(fig, axs, f0_idx, t0, df0, known_message, show_ylabels = True, peak = 0):

    axPF, axP, axL = axs

    for ax in fig.axes:
        ax.set_yticks(np.array([0,0]),labels = ['',''])
        ax.set_xticks(np.array([0,0]),labels = ['',''])
    
    def colour_background(x, dBval):
        x[(x<dBval)] = dBval
    

    pF = pgrid_main[:79, f0_idx: f0_idx + 8 * OSAMP_FREQ]
    centres = [b * OSAMP_FREQ + OSAMP_FREQ//2 for b in range(8)]
    p = pF[:, centres]

    dBrange = 30
    dBF = calc_dB(pF, dBrange = dBrange, rel_to_max = False)
    colour_background(dBF[:7],-20)
    colour_background(dBF[36:43],-20)
    colour_background(dBF[72:],-20)
    im = axPF.imshow(dBF, origin="lower", aspect="auto", 
                cmap="inferno", interpolation="none", alpha = 0.8, vmax = peak, vmin = peak - dBrange)
    
    dBrange = 20
    dB = calc_dB(p, dBrange = dBrange, rel_to_max = False)
    colour_background(dB[:7],-10)
    colour_background(dB[36:43],-10)
    colour_background(dB[72:],-10)
    im = axP.imshow(dB, origin="lower", aspect="auto", 
                cmap="inferno", interpolation="none", alpha = 0.8, vmax = peak, vmin = peak - dBrange)
 
    n_tone_errors = 0
    if(known_message is not None):
        symbols = create_symbols(known_message)
        for i, t in enumerate(symbols):
            edge = 'g'
            if (t != np.argmax(dB[i,:])):
                edge = 'r'
                n_tone_errors +=1
            rect = patches.Rectangle((t-0.5 , i -0.5 ),1,1,linewidth=1.5,edgecolor=edge,facecolor='none')
            axP.add_patch(rect)

    llr_full = get_llr(p)
    axL.barh(range(len(llr_full)), llr_full, align='edge')
    axL.set_ylim(0,len(llr_full))
    axL.set_xlim(-5,5)

    ticks = {'Costas1':0, 'C1+r':7,'C2+r+R':16.66,'Grid-rpt+i3':26.66,'CRC':32, 'Costas2':36, 'CRCcont':43,'Parity':44.33,'Costas3':72}
    axPF.set_yticks(np.array([v for k, v in ticks.items()])-0.5)
    axPF.set_yticklabels([k for k, v in ticks.items()] if show_ylabels else "", fontsize = 6)
    axL.set_yticks(np.array([3*v for k, v in ticks.items()])-0.5, labels="")
    
    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    llr = get_llr(p[payload_symb_idxs,:])
    msg, n_its, n_bit_errors = decode(llr)
    fig.suptitle(f"{known_message}, Kaiser = {KAISER_IND}, Freq oversampling = {OSAMP_FREQ}\n DECODED: {msg}")


    axP.set_title(f"{t0:5.2f}s {df0:5.2f}b {n_tone_errors} tone errors", fontsize = 6)
    axL.set_title(f"σ={np.std(llr):5.2f} {n_bit_errors} bit errors", fontsize = 6)

    return np.max(dBF)

def create_ft8_wave(symbols, fs=12000, f_base=873.0, f_step=6.25, amplitude = 0.5):
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
    waveform_int16 = np.int16(waveform * 32767)
    return waveform_int16


def subtract(audio_data, h0_idx, freq_idxs, meth = 'complex'):
    audio_ptr = 0
    grid_ptr = h0_idx
    global zgrid_main, pgrid_main, fft_len, fft_window, nFreqs
    samples_per_symbol = int(SAMPLE_RATE  / 6.25 )
    while(audio_ptr + fft_len < len(audio_data)):
        x = audio_data[audio_ptr: audio_ptr + fft_len] * fft_window
        gen_z = np.fft.rfft(x)[:nFreqs][freq_idxs]
        gen_max_idx = np.argmax(np.abs(gen_z))
        ex_p = pgrid_main[grid_ptr][freq_idxs]
        ex_max_idx = np.argmax(ex_p)
        if(meth == 'complex'):
            ex_z = zgrid_main[grid_ptr][freq_idxs]
            new_z = ex_z - gen_z * ex_z[ex_max_idx] / gen_z[gen_max_idx]
            zgrid_main[grid_ptr][freq_idxs] = new_z
            pgrid_main[grid_ptr][freq_idxs] = new_z.real*new_z.real + new_z.imag*new_z.imag
        else:
            gen_p = gen_z.real*gen_z.real + gen_z.imag * gen_z.imag
            new_p = ex_p - gen_p * ex_p[ex_max_idx] / gen_p[gen_max_idx]
            pgrid_main[grid_ptr][freq_idxs] = new_p
        grid_ptr += 1
        audio_ptr += samples_per_symbol

#======================================================
# investigation section
#======================================================

fig_spec, ax_spec = plt.subplots(figsize = (10,5))
fig_sig, axs_sig = plt.subplots(1, 3, figsize = (5,8))
plt.ion()

signal_info_list = [(2571, 0, 'W1FC F5BZB -08'), (2158, 1.8*.16, 'WM3PEN EA6VQ -09'),
                    (1197, 0, 'CQ F5RXL IN94'), (2852, 0, 'XE2X HA2NP RR73')]
                    
audio_samples = read_wav(WAV_FILE)

freq, t0, known_msg = signal_info_list[1]
f0_idx = int(freq* OSAMP_FREQ /6.25)

get_spectrum(audio_samples, t0, 0, 0)
show_spectrum(fig_spec, ax_spec)
peak = show_sig(fig_sig, axs_sig, f0_idx, t0, 0, known_msg, show_ylabels = True, peak = 120)
plt.pause(1)

symbols = create_symbols(known_msg)
audio_data = create_ft8_wave(symbols, f_base = freq)
freq_idxs = np.array(range(f0_idx - 2, f0_idx + 26))
subtract(audio_data, 1, freq_idxs, 'comp')
show_spectrum(fig_spec, ax_spec)
show_sig(fig_sig, axs_sig, f0_idx, t0, 0, known_msg, show_ylabels = True, peak = 120)

plt.pause(1)
