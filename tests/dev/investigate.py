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

def get_spectrum(audio_samples, time_offset, phase_global, phase_per_symbol, max_freq = 3100):
    hops_per_cycle = int(15 * 6.25)
    samples_per_hop = int(12000  / 6.25 )
    fft_len = 1920
    fft_window=np.kaiser(fft_len, 5) 
    nFreqs = int(max_freq/6.25)
    samples_offset = int(time_offset * 12000)
    pf = np.zeros((hops_per_cycle, nFreqs), dtype = np.float32)
    for hop_idx in range(hops_per_cycle):
        phs = np.linspace(0, phase_global + hop_idx * phase_per_symbol, fft_len)
        za = np.zeros_like(fft_window, dtype = np.complex64)
        aud = audio_samples[samples_offset + hop_idx * samples_per_hop: samples_offset+ hop_idx * samples_per_hop + fft_len]
        za[:len(aud)] = aud
        za = za *fft_window * np.exp(1j * phs)
        z = np.fft.fft(za)[:nFreqs]
        p = z.real*z.real + z.imag*z.imag
        pf[hop_idx, :] = p
    return pf

def get_tsyncs(p):
    costas=[3,1,4,0,6,5,2]
    csync = np.full((len(costas), len(costas)), -1/7, np.float32)
    for sym_idx, tone in enumerate(costas):
        csync[sym_idx:sym_idx+1, tone:tone+1] = 1.0
    syncs = []
    block_off = 36
    hop_start_lattitude = int(2 * 6.25 )
    hop_idxs_Costas =  np.arange(len(costas)) 
    f_idxs = np.arange(len(costas)) 
    pnorm = p[:, f_idxs]
    pnorm = pnorm / np.max(pnorm)
    for iBlock in [0,1]:
        best = (0, -1e30)
        for h0_idx in range(block_off * iBlock, block_off * iBlock + hop_start_lattitude):
           # sync_score = float(np.dot(pnorm[h0_idx+hop_idxs_Costas,:].ravel(), csync.ravel()))
            sync_score = np.sum(pnorm[h0_idx+hop_idxs_Costas,:] * csync)
            test = (h0_idx - block_off * iBlock, sync_score)
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

global im
im = None
def show_sig(ax, p1, dBrange, f0_idx, known_message):
    global im
    p = p1[:, f0_idx:f0_idx+8]
    tsyncs = get_tsyncs(pf)
    h0_idx = tsyncs[1][0]
    print("tsyncs hardwired to 3")
    h0_idx = 0
    
    symbols = create_symbols(known_message)
    pvt = np.mean(p + 0.001, axis = 1)
    p = p / pvt[:,None]

    for s in range(p.shape[0]):
        ps = p[s,:]
        p[s, np.argmax(ps)]=2
    dB = calc_dB(p, dBrange = dBrange, rel_to_max = True)
    if(im):
        im.set_data(dB)
    else:
        im = axs[0].imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)

    ax2 = plt.gca()
    n_tone_errors = 0
    for i, t in enumerate(symbols):
        edge = 'g'
        if (t != np.argmax(dB[h0_idx+i,:])):
            edge = 'r'
            n_tone_errors +=1
        if (i<=6) or i>=72 or (i>=36 and i<=42): edge = 'b'
        rect = patches.Rectangle((t-0.5 , i + h0_idx-0.5 ),1,1,linewidth=1.5,edgecolor=edge,facecolor='none')
        axs[0].add_patch(rect)

    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    llr_full = get_llr(p)
    axs[1].barh(range(len(llr_full)), llr_full, align='edge')
    axs[1].set_ylim(0,len(llr_full))
    axs[1].set_xlim(-5,5)

    llr = get_llr(p[h0_idx:,:][payload_symb_idxs,:])
    print(len(llr))
    msg = decode(llr)

    fig.suptitle(f"{signal[1]}\n{f0_idx*6.25:5.1f}Hz {0.16*h0_idx:5.2f}s Tone errors:{n_tone_errors}\n{msg}")
    

signal_info_list = [(2571, 'W1FC F5BZB -08'), (2157, 'WM3PEN EA6VQ -09')]
                    
audio_samples = read_wav("../data/210703_133430.wav")


# what's the best way to incorporate possible time and frequency offsets and slopes automatically?

signal = signal_info_list[1]
freq, msg = signal
f0_idx = int(freq/6.25)
fig,axs = plt.subplots(1,2, figsize = (5,10))
plt.ion()
pf = get_spectrum(audio_samples, 2.8 * 0.16, -1.3, 0/80)
print(pf.shape)
show_spectrum(pf)
show_sig(axs, pf, 6, f0_idx, msg)
plt.pause(0.1)
    
gray_seq = [0,1,3,2,5,6,4,7]
gray_map = np.array([[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]])
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))


