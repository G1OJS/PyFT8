import numpy as np
import matplotlib.pyplot as plt

HPS=1
BPT=1
SYM_RATE=6.25
SAMP_RATE=12000
T_CYC=15
HOPS_PER_CYCLE = int(T_CYC*SYM_RATE*HPS)
BASE_FREQ_IDXS = np.array([BPT * t for t in range(8)])
NBITS = 9
NSYMS = int(NBITS//3)
#GRAY CODE
# Tone  Bits
#   0   000 (0)
#   1   001 (1)
#   2   011 (*3)
#   3   010 (*2)
#   4   110 (*6)
#   5   100 (*4)
#   6   101 (*5)
#   7   111 (7)
GRAY = [0,1,3,2,5,6,4,7]
unGRAY = [0,1,3,2,6,4,5,7]

#============== Transmitter ========================================================
def gray_encode(bits):
    syms = []
    for _ in range(NSYMS):
        chunk = bits & 0x7
        syms.insert(0, GRAY[chunk])
        bits >>= 3
    return syms

def create_ft8_wave(channel_symbols, fs=12000, f_base=100.0, f_step=6.25, amplitude = 0.5):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    start_sample = int(fs*0.0)
    phase = 0
    waveform = []
    for s in channel_symbols:
        f = f_base + s * f_step 
        phase_inc = 2 * np.pi * f / fs 
        w = np.sin(phase + phase_inc * np.arange(symbol_len))
        waveform.append(w)
        phase = (phase + phase_inc * symbol_len) % (2 * np.pi)
    waveform = np.concatenate(waveform).astype(np.float32)
    waveform = waveform.astype(np.float32)
    waveform = amplitude * waveform / np.max(np.abs(waveform))
    return waveform
#============== Receiver ========================================================

def addNoise(z, added_noise_dB):
    noise = np.random.randn(len(z)) + 1j*np.random.randn(len(z))
    signal_rms = np.sqrt(np.mean(np.abs(z)**2))
    noise_rms_needed = signal_rms * 10**(added_noise_dB / 20)
    noise *= noise_rms_needed / np.sqrt(np.mean(np.abs(noise)**2))
    return z + noise

def spectrum(audio, max_freq = 300, noise_dB = -50):
    fft_len = int(BPT * SAMP_RATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
    fft_window = np.hanning(fft_len).astype(np.float32)
    fft_phase = np.linspace(0, np.pi, fft_len)
    df = max_freq / nFreqs
    samps_perhop = int(SAMP_RATE // (HPS*SYM_RATE))
    spec_pwr = np.ones((NSYMS, nFreqs), dtype = np.float32)
    spec_phase = np.zeros((NSYMS, nFreqs), dtype = np.float32)
    for hop in range(NSYMS):
        s0 = hop*samps_perhop
        aw = audio[s0: s0+fft_len] * fft_window
        aw = audio[s0: s0+fft_len]
        #aw = aw * np.exp(1j * fft_phase)
        z = np.fft.fft(aw)[:nFreqs]
        z = addNoise(z, noise_dB)
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        spec_pwr[hop, :] = p
        spec_phase[hop, :] = np.atan2(z.imag, z.real)
    return spec_pwr, spec_phase, df

def demap_argmax(dBgrid_main, h0_idx, f0_idx, df):
    hops = range(NBITS//3)
    freq_idxs = f0_idx + BASE_FREQ_IDXS
    dBgrid = dBgrid_main[np.ix_(hops, freq_idxs)]
    tones = np.argmax(dBgrid, axis = 1)
    bits_decoded_str = ''.join([f"{unGRAY[t]:03b}" for t in tones])
    llr = [-1+2*int(b) for b in bits_decoded_str]
    return llr

def demap(dBgrid_main, h0_idx, f0_idx, df):
    freq_idxs = f0_idx + BASE_FREQ_IDXS
    hops = range(NBITS//3)
    p = dBgrid_main[np.ix_(hops, freq_idxs)]
    pmax = np.max(p)
    snr = np.clip(int(pmax - np.min(p) - 58), -24, 24)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc))
    llr = llr.ravel() 
    return np.clip(llr,-6,6)

#============== Charts ========================================================
def annotated_imshow(ax, vals, title = ''):
    ax.imshow(vals, origin = 'lower', aspect = 'auto', interpolation = 'nearest')
    ax.set_title(title)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            text = ax.text(j, i, f"{vals[i, j]:4.1f}", ha="center", va="center", color="w")

def show_spectrum(dBgrid_main, phase, f0, fn):
    fig, axs = plt.subplots(2, figsize=(4,12))
    annotated_imshow(axs[0], dBgrid_main[:,f0:fn], "Signal amplitude")
    annotated_imshow(axs[1], phase[:,f0:fn], "Signal phase")

def show_llr(encoded_bits174_str, llr, llr_hard):
    fig, ax = plt.subplots(figsize=(15,4))
    encoded_bits174 = [-1+2*int(b) for b in encoded_bits174_str]
    ax.set_title(f"Demapped LLR overlaid on transmitted payload bits with {noise_dB}dB added noise")
    ax.plot(encoded_bits174, label = 'Encoded bits')
    ax.plot(llr, label = f"llr ({assess_llr(transmitted_payload_bits, llr)} bit errors)")
    ax.plot(llr_hard, label = f"llr_hard ({assess_llr(transmitted_payload_bits, llr_hard)} bit errors)")
    plt.legend()

def assess_llr(transmitted_payload_bits, llr):
    recovered_payload_bits_unGrayed_str = ''.join([f"{b}" for b in (np.array(llr) > 0).astype(int)])
    print(f"{recovered_payload_bits_unGrayed_str=         }")
    recovered_payload_symbols_unGrayed_str = ''.join([f"{int('0b'+s,2)}" for s in [recovered_payload_bits_unGrayed_str[i*3:i*3+3] for i in range(NBITS//3)] ] )
    inferred_payload_symbols_str = ''.join([str(GRAY[int(s)]) for s in recovered_payload_symbols_unGrayed_str])
    print(f"{inferred_payload_symbols_str=                }")
    bit_errors = [1 if a!=recovered_payload_bits_unGrayed_str[i] else 0 for i, a in enumerate(transmitted_payload_bits)]
    print(f"Bit errors {np.sum(bit_errors)}")
    return np.sum(bit_errors)

#============== Main ========================================================

print("**Now internally consistent and ready to test alternative demappers e.g. correlated**")
print("**Also worth looking at refactoring to allow montecarlo tests against added noise levels**")
print("**Could strip out the faithful bits174_int generation and use random**\n")

bits_int = 0b110000011
f_base = 40*6.25
noise_dB = -25

channel_symbols = gray_encode(bits_int)

transmitted_payload_bits = f"{bits_int:03b}"
print(f"{transmitted_payload_bits =                   }")
transmitted_payload_symbols_str = ''.join([str(s) for s in channel_symbols])
print(f"{transmitted_payload_symbols_str=             }")

audio = create_ft8_wave(channel_symbols, f_base = f_base)
power, phase, df = spectrum(audio, max_freq = 3000, noise_dB = noise_dB)
f0_idx = int(f_base / df)

dBgrid_main = 20*np.log10(power)
dBgrid_main = np.clip(dBgrid_main, np.max(dBgrid_main)-20, None)
show_spectrum(dBgrid_main, phase, f0_idx, f0_idx + 8*BPT)

llr = demap(power, 0, f0_idx, df)
llr_hard = demap_argmax(dBgrid_main, 0, f0_idx, df)
show_llr(transmitted_payload_bits, llr, llr_hard)


plt.show()



