import numpy as np
import wave
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LogNorm
from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77

hps=3
bpt=3

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

def get_spectrum(audio_samples):
    hops_per_cycle = int(15 * 6.25 * hps)
    samples_per_hop = int(12000  / (6.25 * hps))
    print(samples_per_hop)
    fft_len = 1920 * bpt
    fft_out_len = fft_len//2 + 1
    fft_window=np.kaiser(fft_len, 7)
    pf = np.zeros((hops_per_cycle, fft_out_len), dtype = np.float32)
    for hop_idx in range(hops_per_cycle):
        x = np.zeros_like(fft_window)
        aud = audio_samples[hop_idx * samples_per_hop: hop_idx * samples_per_hop + fft_len]
        x[:len(aud)] = aud
        x*=fft_window
        z = np.fft.rfft(x)
        p = z.real*z.real + z.imag*z.imag
        pf[hop_idx, :] = p
    return pf

def get_tsyncs(p):
    costas=[3,1,4,0,6,5,2]
    csync = np.full((len(costas)*hps, len(costas)*bpt), -1/(7*bpt), np.float32)
    for sym_idx, tone in enumerate(costas):
        csync[sym_idx*hps:(sym_idx+1)*hps, tone*bpt:(tone+1)*bpt] = 1.0
    syncs = []
    block_off = 36 * hps
    hop_start_lattitude = int(2 * 6.25 * hps)
    hop_idxs_Costas =  np.arange(len(costas)* hps) 
    f_idxs = np.arange(len(costas)* bpt) 
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
    
def show_llr(ax,llr, tone):
    ax.barh(range(len(llr)), llr, align='edge')
    ax.set_ylim(0,len(llr))
    ax.set_xlim(-10,10)

def get_llr(p):
    hops = np.array([i*hps + hps//2 for i in range(int(p.shape[0]//hps))])
    freqs = np.array([i*bpt + bpt//2 for i in range(int(p.shape[1]//bpt))])
    p = p[hops,:][:,freqs]
    pvt = np.mean(p + 0.001, axis = 1)
    p = p / pvt[:,None]
    p = calc_dB(p, dBrange = 30)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    llr = 3.8*llr/np.std(llr)
    return llr, np.argmax(p, axis = 1)

def show_sig(p1, dBrange, h0_idx, symbols):
    fig,axs = plt.subplots(1,2, figsize = (5,10))
    pvt = np.mean(p1 + 0.001, axis = 1)
    p = p1 / pvt[:,None]
    dB = calc_dB(p, dBrange = dBrange, rel_to_max = True)
    im = axs[0].imshow(dB, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", alpha = 0.8)
    ax2 = plt.gca()
    for i, t in enumerate(symbols):
        edge = 'g' if (i<=7) or i>=72 or (i>=36 and i<=43) else 'r'
        rect = patches.Rectangle((bpt*t -bpt//2, hps*i + h0_idx - hps//2),bpt,hps,linewidth=2,edgecolor=edge,facecolor='none')
        axs[0].add_patch(rect)
   # fig.suptitle(f"{signal[1]}\n{signal[0]*6.25/bpt:5.1f}Hz {0.16*signal[1]/hps:5.2f}s")
    plt.show()


signal_info_list = [(2571, 'W1FC F5BZB -08'), (2157, 'WM3PEN EA6VQ -09')]
                    
audio_samples = read_wav("../data/210703_133430.wav")
pf = get_spectrum(audio_samples)

for signal in signal_info_list:
    freq, msg = signal
    f0_idx = int(bpt*freq/6.25)
    p = pf[:, f0_idx:f0_idx+8*bpt]
    tsyncs = get_tsyncs(p)
    h0_idx = tsyncs[0][0]
    symbols = create_symbols(msg)
    show_sig(p, 20, h0_idx, symbols)

gray_seq = [0,1,3,2,5,6,4,7]
gray_map = np.array([[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]])
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))


