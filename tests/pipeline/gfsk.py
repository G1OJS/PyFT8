import numpy as np

SAMPLE_RATE = 12000
N_SYMS = 79
SYM_RATE = 6.25
samples_per_symbol = 1920

def gen_pulse(bt = 2.0):
    from scipy.special import erf
    ibt = int(0.5 + 10*bt)
    fchk = N_SYMS + samples_per_symbol + bt + SAMPLE_RATE
    c = np.pi*np.sqrt(2.0/np.log(2.0))
    pulse = np.zeros(3*samples_per_symbol)
    for i in range(3*samples_per_symbol):
        tt = (i-1.5*samples_per_symbol) / samples_per_symbol
        pulse[i] = 0.5*(erf(c*bt*(tt+0.5))-erf(c*bt*(tt-0.5)))
    return pulse

def symbols_to_complex_audio(symbols, f0 = 100):
    samps_per_sym = SAMPLE_RATE / SYM_RATE
    dphi_peak = 2.0*np.pi / samples_per_symbol
    nsamps = int(samps_per_sym*(len(symbols)+2))
    dphi = np.zeros(nsamps)
    for isym, tone in enumerate(symbols):
        samp0 = isym * samples_per_symbol
        t0 = isym * 0.16
        dphi[samp0: samp0 + len(pulse)] += dphi_peak * pulse * tone
    phi = np.add.accumulate(dphi) + 2*np.pi*f0*np.arange(nsamps)/SAMPLE_RATE
    wf = np.exp(1j * (phi % (2*np.pi)))
    return wf

import matplotlib.pyplot as plt
fig, ax = plt.subplots()

pulse = gen_pulse()
wf = symbols_to_complex_audio([0,7,4,2])
ax.plot(np.real(wf))

plt.show()
