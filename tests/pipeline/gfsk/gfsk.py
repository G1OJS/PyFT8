import numpy as np

SAMP_RATE = 12000
SYM_RATE  = 6.25

def gen_pulse(bt = 2.0):
    from scipy.special import erf
    samps_per_sym = int(SAMP_RATE / SYM_RATE)
    c = np.pi*np.sqrt(2.0/np.log(2.0))
    pulse = np.zeros(3*samps_per_sym)
    for i in range(3*samps_per_sym):
        tt = (i-1.5*samps_per_sym) / samps_per_sym
        pulse[i] = 0.5*(erf(c*bt*(tt+0.5))-erf(c*bt*(tt-0.5)))
    return pulse
pulse = gen_pulse()

def symbols_to_complex_audio(symbols, f_base = 873):
    samps_per_sym = int(SAMP_RATE / SYM_RATE)
    dphi_peak = 2.0*np.pi / samps_per_sym
    nsamps = int(samps_per_sym*(len(symbols)+2))
    dphi = np.zeros(nsamps)
    for isym, tone in enumerate(symbols):
        samp0 = isym * samps_per_sym
        t0 = isym * 0.16
        dphi[samp0: samp0 + len(pulse)] += dphi_peak * pulse * tone
    phi = np.add.accumulate(dphi) + 2*np.pi*f_base*np.arange(nsamps)/SAMP_RATE
    phi[:2*samps_per_sym] += dphi_peak * pulse[ samps_per_sym:] * symbols[0]
    phi[-2*samps_per_sym:] += dphi_peak * pulse[:-samps_per_sym] * symbols[-1]
    phi = phi[samps_per_sym:-samps_per_sym]
    wf = np.exp(1j * (phi % (2*np.pi)))
    nramp = int(0.5 + samps_per_sym / 8.0)
    cosramp = np.cos(np.linspace(0, np.pi, nramp))
    wf[:nramp] *= (1 - cosramp) / 2.0
    wf[-nramp:] *= (1 + cosramp) / 2.0
    return wf

def symbols_to_audio_bytes(symbols, fs = SAMP_RATE, f_base=873.0, amplitude = 0.5):
    waveform = np.imag(symbols_to_complex_audio(symbols))
    waveform = waveform.astype(np.float32)
    waveform = amplitude * waveform / np.max(np.abs(waveform))
    waveform_bytes = np.int16(waveform * 32767).tobytes()
    return waveform_bytes

# =========== demo / test code =======================

syms = [0]*79
demo_syms = [0,4,0,6,0,4,0]
syms[:len(demo_syms)] = demo_syms
syms[-len(demo_syms):] = demo_syms
a = symbols_to_complex_audio(syms, f_base = 100)
samps_per_sym = int(SAMP_RATE / SYM_RATE)
print(len(a)/samps_per_sym)
demo_samps = len(demo_syms) * int(SAMP_RATE / SYM_RATE)
import matplotlib.pyplot as plt
fig, axs = plt.subplots(2,1,figsize=(8,5))
axs[0].plot(np.imag(a)[:demo_samps])
axs[1].plot(np.imag(a)[-demo_samps:])
plt.show()
