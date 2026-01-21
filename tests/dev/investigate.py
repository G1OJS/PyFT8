import numpy as np
import wave
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.ldpc import LdpcDecoder

def decode(llr):
    llr0 = llr.copy()
    ldpc = LdpcDecoder()
    ncheck = ldpc.calc_ncheck(llr)
    n_its = 0
    if(ncheck > 0):
        for n_its in range(1, 10):
            llr, ncheck = ldpc.do_ldpc_iteration(llr)
            if(ncheck == 0):break
    msg = "Not decoded"
    n_err = "?"
    if(ncheck == 0):
        cw_bits = (llr > 0).astype(int).tolist()
        msg = FT8_unpack(cw_bits)
        n_err = np.count_nonzero(np.sign(llr) != np.sign(llr0))
    return f"{msg} in {n_its} its, bit errs = {n_err}"

def read_wav(wav_path):
    samples_per_cycle = 15 * 12000
    wf = wave.open(wav_path, "rb")
    ptr = 0
    frames = True
    audio_samples = np.zeros((samples_per_cycle), dtype = np.float32)
    while frames:
        frames = wf.readframes(12000)
        if(frames):
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            ns = len(samples)
            audio_samples[ptr:ptr+ns]= samples
            ptr += ns
    print(f"Loaded {ptr} samples")
    return audio_samples

def get_spectrum(audio_samples, time_offset, phase_global, phase_per_symbol, max_freq = 3100, nSyms = 79):
    samples_per_symbol = int(12000  / 6.25 )
    fft_len = 1920
    fft_window=np.kaiser(fft_len, 5) 
    nFreqs = int(max_freq/6.25)
    samples_offset = int(time_offset * 12000)
    pf = np.zeros((nSyms, nFreqs), dtype = np.float32)
    for sym_idx in range(nSyms):
        phs = np.pi*np.linspace(0, phase_global + sym_idx * phase_per_symbol, fft_len)
        za = np.zeros_like(fft_window, dtype = np.complex64)
        aud = audio_samples[samples_offset + sym_idx * samples_per_symbol: samples_offset + sym_idx * samples_per_symbol + fft_len]
        za[:len(aud)] = aud
        za = za *fft_window * np.exp(1j * phs)
        z = np.fft.fft(za)[:nFreqs]
        p = z.real*z.real + z.imag*z.imag
        pf[sym_idx, :] = p
    return pf

def get_tsyncs(f0_idx):
    costas=[3,1,4,0,6,5,2]
    csync = np.full((len(costas), 8), -1/7, np.float32)
    for sym_idx, tone in enumerate(costas):
        csync[sym_idx, tone] = 1.0
    syncs = []
    block_off = 36
    for iBlock in [0,1]:
        best = (0, -1e30)
        for t0 in np.arange(-1,2,.016):
            pf = get_spectrum(audio_samples, t0 + iBlock*36*0.16, 0, 0, nSyms = 7)
            pnorm = pf[:, f0_idx:f0_idx+8]
            pnorm = pnorm / np.max(pnorm)
            # sync_score = float(np.dot(pnorm[h0_idx+hop_idxs_Costas,:].ravel(), csync.ravel()))
            sync_score = np.sum(pnorm * csync)
            test = (t0, sync_score)
            if test[1] > best[1]:
                best = test 
        syncs.append(best)
    return syncs

def create_symbols(msg):
    msg = msg.split(" ")
    c28a = pack_ft8_c28(msg[0]) 
    c28b = pack_ft8_c28(msg[1])
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

def show_spectrum(p1, dBrange = 40):
    fig,ax = plt.subplots(figsize = (10,5))
    dB = calc_dB(p1, dBrange = dBrange, rel_to_max = True)
    im = ax.imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)
    plt.show()


def show_sig(ax, p1, f0_idx, known_message):
    p = p1[:79, f0_idx:f0_idx+8]

    symbols = create_symbols(known_message)
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
    
    im = axs[0].imshow(dB, origin="lower", aspect="auto", 
                cmap="inferno", interpolation="none", alpha = 0.8)
 

    ax2 = plt.gca()
    n_tone_errors = 0
    for i, t in enumerate(symbols):
        edge = 'g'
        if (t != np.argmax(dB[i,:])):
            edge = 'r'
            n_tone_errors +=1
        rect = patches.Rectangle((t-0.5 , i -0.5 ),1,1,linewidth=1.5,edgecolor=edge,facecolor='none')
        axs[0].add_patch(rect)

    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    llr_full = get_llr(p)
    axs[1].barh(range(len(llr_full)), llr_full, align='edge')
    axs[1].set_ylim(0,len(llr_full))
    axs[1].set_xlim(-5,5)

    ticks = {'Costas1':0, 'C1+r':7,'C2+r+R':16.66,'Grid-rpt+i3':26.66,'CRC':32, 'Costas2':36, 'CRCcont':43,'Parity':44.33,'Costas3':72}
    axs[0].set_yticks(np.array([v for k, v in ticks.items()])-0.5, labels=[k for k, v in ticks.items()])
    axs[1].set_yticks(np.array([3*v for k, v in ticks.items()])-0.5, labels="")    

    llr = get_llr(p[payload_symb_idxs,:])
    nbad = np.count_nonzero(np.abs(llr<0.5))
    msg = decode(llr)

    return n_tone_errors, llr, msg 

signal_info_list = [(2571, 'W1FC F5BZB -08', 0.5, 0), (2157, 'WM3PEN EA6VQ -09',  1, 0),
                    (1197, 'CQ F5RXL IN94', -1.1, 0), (2852, 'XE2X HA2NP RR73', -1, 0)]
                    
audio_samples = read_wav("../data/210703_133430.wav")


# what's the best way to incorporate possible time and frequency offsets and slopes automatically?

signal = signal_info_list[3]
freq, known_msg, df0, fd_per_sym = signal
f0_idx = int(freq/6.25)

tsyncs = get_tsyncs(f0_idx)
for s in tsyncs:
    print(f"{s[0]:5.2f} {s[1]:5.2f}")
    t0 = s[0]
    pf = get_spectrum(audio_samples, t0, df0, fd_per_sym)
    fig, axs = plt.subplots(1,2, figsize = (5,10))
    n_tone_errors, llr, decoded_msg = show_sig(axs, pf, f0_idx, known_msg)
    fig.suptitle(f"{signal[1]}\nT0 {t0:5.2f} df0 {df0:5.2f} \nTone errors:{n_tone_errors}   σ(llr): {np.std(llr):5.2f}\n{decoded_msg}")
plt.show()
    
gray_seq = [0,1,3,2,5,6,4,7]
gray_map = np.array([[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]])
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))


