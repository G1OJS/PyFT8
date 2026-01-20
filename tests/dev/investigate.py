import numpy as np
import wave
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77

hps=1
bpt=3

def wav_to_spectrum(wav_path):
    fft_len = 1920 * bpt
    fft_out_len = fft_len//2 + 1
    hop_rate = int(6.25 * hps)
    hops_per_cycle = 15 * hop_rate
    zf = np.zeros((hops_per_cycle, fft_out_len), dtype = np.complex64)
    pf = np.zeros((hops_per_cycle, fft_out_len), dtype = np.complex64)
    
    fft_window=np.kaiser(fft_len, 20)
    wf = wave.open(wav_path, "rb")
    ptr = 0
    frames = True
    audio_samples = np.zeros((hops_per_cycle), dtype = np.complex64)
    while frames:
        frames = wf.readframes(1)
        if(frames):
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            print(len(samples))
            if(len(samples) == fft_len):
                x = samples * fft_window
                z = np.fft.rfft(x)
                p = z.real*z.real + z.imag*z.imag
                zf[ptr, :] = z
                pf[ptr, :] = p
                ptr = (ptr + 1) % hops_per_cycle
    print(f"Loaded {ptr} hops")
    return zf, pf

def create_mask(msg):
    msg = msg.split(" ")
    c28a = pack_ft8_c28(msg[0]) 
    c28b = pack_ft8_c28(msg[1])
    g15, ir = pack_ft8_g15(msg[2])
    i3 = 1
    n3 = 0
    bits77 = (c28a<<28+1+2+15+3) | (c28b<<2+15+3)|(0<<15+3)|(g15<< 3)|(i3)
    symbols, bits174_int, bits91_int, bits14_int, bits83_int = encode_bits77(bits77)
    return np.array([[int(i/bpt)==tone for i in range(bpt * 8)] for tone in symbols for j in range(hps)])

def calc_dB(pwr, dBrange = 20, rel_to_max = False):
    thresh = np.max(pwr) * 10**(-dBrange/10)
    pwr = np.clip(pwr, thresh, None)
    dB = 10*np.log10(pwr)
    if(rel_to_max):
        dB = dB - np.max(dB)
    return dB

def show_power(ax, z, dBrange = 10, mask = None):
    p = np.abs(z)**2
    pvt = np.mean(p + 0.001, axis = 1)
    p = p / pvt[:,None]
    alpha_mask = np.zeros_like(p) + 1
    if(mask is not None):
        p_masked = np.ma.masked_array(p, mask)
        dB = calc_dB(p_masked, dBrange = dBrange, rel_to_max = True)
        im = ax.imshow(dB, origin="lower", aspect="auto", 
                        cmap="grey", interpolation="none", alpha = 0.6)
        p = np.ma.masked_array(p, (mask==False))
    dB = calc_dB(p, dBrange = dBrange, rel_to_max = True)
    im = ax.imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)
    
def show_phase(ax, z, mask = None):
    phs = np.angle(z)
    alpha_mask = np.zeros_like(phs) + 1
    if(mask is not None):
        alpha_mask[(mask==False)] = 0.5
    im1 = ax.imshow(phs, origin="lower", aspect="auto", 
                    cmap="twilight", interpolation="none", alpha = alpha_mask)
    im1.norm.vmin = -3.14
    im1.norm.vmax = 3.14

def show_llr(ax,llr, tone):
    ax.barh(range(len(llr)), llr, align='edge')
    ax.set_ylim(0,len(llr))
    ax.set_xlim(-10,10)

def get_llr(zf):
    hops = np.array([i*hps + hps//2 for i in range(int(zf.shape[0]//hps))])
    freqs = np.array([i*bpt + bpt//2 for i in range(int(zf.shape[1]//bpt))])
    p = np.abs(zf[hops,:][:,freqs])**2
    pvt = np.mean(p + 0.001, axis = 1)
    p = p / pvt[:,None]
    p = calc_dB(p, dBrange = 30)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    llr = 3.8*llr/np.std(llr)
    return llr, np.argmax(p, axis = 1)

def show_sig(zf, signal, dBrange = 10, symbols = [0,79]):
    hop_idxs = np.array(range(signal[1]-hps//2, signal[1]+79*hps-hps//2))
    hop_idxs = np.clip(hop_idxs, 0, zf.shape[0]-1)
    print(hop_idxs)
    print(zf.shape)
    zf = zf[hop_idxs, signal[0]:signal[0]+8*bpt]
    mask = create_mask(signal[2])
    fig,axs = plt.subplots(1,2, figsize = (5,10))
    z = zf[symbols[0]*hps :symbols[1]*hps, :]
    mask = mask[symbols[0]*hps :symbols[1]*hps, :]
    show_power(axs[0], z, dBrange = dBrange, mask = mask)
    llr, tone = get_llr(z)
    show_llr(axs[1],llr, tone)
    fig.suptitle(signal[2])
    plt.show()


signal_info_list = [(1233, 33, 'W1FC F5BZB -08'), (1034, 23, 'WM3PEN EA6VQ -09'), (574, 1, 'CQ F5RXL IN94'), (306, 33, 'N1JFU EA6EE R-07'), (346, 29, 'A92EE F5PSR -14'), (1293, 21, 'K1BZM EA3GP -09'), (191, 33, 'W0RSJ EA3BMU RR73'), (282, 34, 'K1JT HA0DU KN07'), (1311, 37, 'W1DIG SV9CVY -14'), (790, 28, 'K1JT EA3AGB -15'), (1368, 31, 'XE2X HA2NP RR73'), (1209, 56, 'K1BZM EA3CJ JN01'), (1220, 49, 'WA2FZW DL5AXX RR73'), (1073, 33, 'N1API HA6FQ -23'), (222, 33, 'N1PJT HB9CQK -10'), (725, 46, 'N1API F2VX 73'), (977, 27, 'K1JT HA5WA 73'), (225, 39, 'KD2UGC F6GCP R-23'), (1094, 28, 'CQ EA2BFM IN83')]

zf, zp = wav_to_spectrum("../data/210703_133430.wav")

for signal_info in signal_info_list:
    show_sig(zf, signal_info, dBrange = 20, symbols = [0,79])

gray_seq = [0,1,3,2,5,6,4,7]
gray_map = np.array([[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]])
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
costas=[3,1,4,0,6,5,2]

