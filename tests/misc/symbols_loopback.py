import numpy as np
import matplotlib.pyplot as plt
import pyaudio

HPS=4
BPT=1
SYM_RATE=6.25
SAMP_RATE=12000
T_CYC=2
NSYMS = 5
HOPS_PER_CYCLE = int(T_CYC*SYM_RATE*HPS)

def create_ft8_wave(symbols, fs=12000, f_base=100.0, f_step=6.25, amplitude = 0.5, added_noise = -50):
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
        waveform += noise
    outframe = np.zeros(int(T_CYC*SAMP_RATE))
    outframe[:len(waveform)] = waveform
    return outframe

def spectrum(audio, max_freq = 300):
    fft_len = int(BPT * SAMP_RATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
    fft_window = fft_window=np.hanning(fft_len).astype(np.float32)
    dt = T_CYC / HOPS_PER_CYCLE
    df = max_freq / (nFreqs - 1)
    samps_perhop = int(SAMP_RATE // (HPS*SYM_RATE))
    print(HOPS_PER_CYCLE, nFreqs)
    spec_pwr = np.ones((HOPS_PER_CYCLE, nFreqs), dtype = np.float32)
    spec_phase = np.zeros((HOPS_PER_CYCLE, nFreqs), dtype = np.float32)
    for hop in range(NSYMS*HPS):
        s0 = hop*samps_perhop
        aw = audio[s0: s0+fft_len] * fft_window
        z = np.fft.rfft(aw)[:nFreqs]
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        spec_pwr[hop, :] = p
        spec_phase[hop, :] = np.atan2(z.imag, z.real)
    return spec_pwr, spec_phase, df

                
def demap(spec, df):
    hops = [i*HPS for i in range(NSYMS)]
    idx = np.argmax(spec[hops,:], axis = 1)/BPT - int(100/(BPT*df)) - 1
    idx = np.clip(idx, 0, 7)
    return idx

#symbols = (8*np.random.rand(NSYMS)).astype(int)
symbols = [3,1,4,0,6,5,2,0,0,0,0,0,0,0,0,1,0,0,5,5,0,0,1,4,0,2,0,7,4,0,5,5,2,2,1,3,3,1,4,0,6,5,2,0,6,1,3,0,0,6,3,7,7,5,3,0,6,1,2,6,3,1,1,5,3,0,7,0,0,7,3,3,3,1,4,0,6,5,2]
symbols = [0,2,0,2]
audio = create_ft8_wave(symbols[:NSYMS], added_noise = -20)
spec, phase, df = spectrum(audio)

fig, axs = plt.subplots(2)
dB = 20*np.log10(spec)
dB = np.clip(dB, np.max(dB)-20, None)
demapped_symbols = demap(dB, df)
axs[0].imshow(dB, origin = 'lower')
axs[1].imshow(phase, origin = 'lower')
plt.show()

fig, ax = plt.subplots()
ax.plot(symbols)
ax.plot(demapped_symbols)
plt.show()
