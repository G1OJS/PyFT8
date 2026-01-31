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
    samples_per_symbol = int(SAMPLE_RATE  / 6.25 )
    fft_len = OSAMP_FREQ * samples_per_symbol
    fft_window=np.kaiser(fft_len, KAISER_IND)
    fft_out_len = fft_len//2 +1
    fft_df = SAMPLE_RATE / fft_out_len
    nFreqs = int(max_freq / fft_df)
    samples_offset = int(time_offset * SAMPLE_RATE)
    pf = np.zeros((nSyms, nFreqs), dtype = np.float32)
    for sym_idx in range(nSyms):
        phs = np.pi*np.linspace(0, phase_global + sym_idx * phase_per_symbol, fft_len)
        za = np.zeros_like(fft_window, dtype = np.complex64)
        aud = audio_samples[samples_offset + sym_idx * samples_per_symbol: samples_offset + sym_idx * samples_per_symbol + fft_len]
        za[:len(aud)] = aud
        za = za *fft_window * np.exp(1j * phs)
        z = np.fft.fft(za)
        z = z[:-OSAMP_FREQ:OSAMP_FREQ][:nFreqs]
        p = z.real*z.real + z.imag*z.imag
        pf[sym_idx, :] = p
    return pf

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

def show_spectrum(p1, dBrange = 60):
    fig,ax = plt.subplots(figsize = (10,5))
    dB = calc_dB(p1, dBrange = dBrange, rel_to_max = True)
    im = ax.imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)
    plt.show()


def show_sig(axP,axL, p1, f0_idx, t0, df0, known_message = None, show_ylabels = True):
    p = p1[:79, f0_idx:f0_idx+8]

    pvt = np.mean(p + 0.001, axis = 1)
    p = p / pvt[:,None]

    for s in range(p.shape[0]):
        ps = p[s,:]
        p[s, np.argmax(ps)]=2
    dB = calc_dB(p, dBrange = 6, rel_to_max = True)

    def colour_background(x, dBval):
        x[(x<dBval)] = dBval
    colour_background(dB[:7],-4)
    colour_background(dB[36:43],-4)
    colour_background(dB[72:],-4)
    
    im = axP.imshow(dB, origin="lower", aspect="auto", 
                cmap="inferno", interpolation="none", alpha = 0.8)
 
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

    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    llr_full = get_llr(p)
    axL.barh(range(len(llr_full)), llr_full, align='edge')
    axL.set_ylim(0,len(llr_full))
    axL.set_xlim(-5,5)

    ticks = {'Costas1':0, 'C1+r':7,'C2+r+R':16.66,'Grid-rpt+i3':26.66,'CRC':32, 'Costas2':36, 'CRCcont':43,'Parity':44.33,'Costas3':72}
    axP.set_yticks(np.array([v for k, v in ticks.items()])-0.5)
    axP.set_yticklabels([k for k, v in ticks.items()] if show_ylabels else "", fontsize = 6)
    axL.set_yticks(np.array([3*v for k, v in ticks.items()])-0.5, labels="")    

    llr = get_llr(p[payload_symb_idxs,:])
    msg, n_its, n_bit_errors = decode(llr)

    axP.set_title(f"{msg}\n{t0:5.2f}s {df0:5.2f}b {n_tone_errors}x", fontsize = 6)
    axL.set_title(f"σ={np.std(llr):5.2f} {n_bit_errors}x", fontsize = 6)

def get_tsyncs(f0_idx, df):
    costas=[3,1,4,0,6,5,2]
    csync = np.full((len(costas), 8), -1/7, np.float32)
    for sym_idx, tone in enumerate(costas):
        csync[sym_idx, tone] = 1.0
    syncs = []
    block_off = 36
    for iBlock in [0,1]:
        best = (0, -1e30)
        for t0 in np.arange(-1,2,.016):
            pf = get_spectrum(audio_samples, t0 + iBlock*36*0.16, df, 0, nSyms = 7)
            pnorm = pf[:, f0_idx:f0_idx+8]
            pmax = np.max(pnorm)
            if(pmax >0):
                pnorm = pnorm / pmax
                sync_score = np.sum(pnorm * csync)
                test = (t0, sync_score)
                if test[1] > best[1]:
                    best = test 
        syncs.append(best)
    return syncs

def grid_t0df0(known_signal, df0_a, df0_b):
    freq, known_msg = known_signal
    f0_idx = int(0.5+freq/6.25)
    n_finefreqs = 5
    fig, axs = plt.subplots(2, n_finefreqs*2, figsize = (14,8))
    fig.suptitle(f"{known_signal[1]}, Kaiser = {KAISER_IND}, Freq oversampling = {OSAMP_FREQ}")
    for ax in fig.axes:
        ax.set_yticks(np.array([0,0]),labels = ['',''])
        ax.set_xticks(np.array([0,0]),labels = ['',''])
    plt.ion()
    plt.pause(0.1)
    for i, df0 in enumerate(np.linspace(df0_a,df0_b,n_finefreqs)):
        tsyncs = get_tsyncs(f0_idx, df0)
        for j, s in enumerate(tsyncs):
            t0 = s[0]
            pf = get_spectrum(audio_samples, t0, df0, 0)
            show_spectrum(pf)
            show_sig(axs[1-j,2*i],axs[1-j, 2*i+1], pf, f0_idx, t0, df0, known_msg, show_ylabels = (i == 0))
            plt.pause(0.1)

    plt.pause(0.1)


def get_syncs(f0_idx):
    costas=[3,1,4,0,6,5,2]
    csync = np.full((len(costas), 8), -1/7, np.float32)
    for sym_idx, tone in enumerate(costas):
        csync[sym_idx, tone] = 1.0
    syncs = []
    block_off = 36
    for iBlock in [0,1]:
        best = (0, 0, -1e30)
        for df0 in np.arange(-1,1,0.1):
            print(df0)
            for t0 in np.arange(-1,2,.016):
                pf = get_spectrum(audio_samples, t0 + iBlock*36*0.16, df0, 0, nSyms = 7)
                pnorm = pf[:, f0_idx:f0_idx+8]
                pmax = np.max(pnorm)
                if(pmax >0):
                    pnorm = pnorm / pmax
                    sync_score = np.sum(pnorm * csync)
                    test = (t0, df0, sync_score)
                    if test[2] > best[2]:
                        best = test 
        syncs.append(best)
    return syncs



#=======================================================
# investigation section
#=======================================================

signal_info_list = [(2571, 'W1FC F5BZB -08'), (2157, 'WM3PEN EA6VQ -09'),
                    (1197, 'CQ F5RXL IN94'), (2852, 'XE2X HA2NP RR73')]
                    
audio_samples = read_wav(WAV_FILE)



grid_t0df0(signal_info_list[1], -1,1)

