import numpy as np
import wave
from PyFT8.decoders import ldpc_decode, osd_012, crc_unpack91

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

SAMP_RATE = 12000
SYM_RATE = 6.25
N_SYMS = 79
T_CYC = 15
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))


def read_wav(wav_file = 'test_08.wav'):
    wf = wave.open(wav_file, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
    wf.close()
    return samps_in

def dB_to_llr(payload_dB_grid):
    p = payload_dB_grid 
    snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    mean = np.mean(llr)
    var = np.mean(llr*llr) - mean*mean
    llr_sd = np.sqrt(var)
    llr = 2.83 * llr / llr_sd
    return llr

def get_candidate_tfgrid(all_audio_spectrum, origin):
    fft2_len = 3200
    fft1_len = len(all_audio_spectrum)
    candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
    candidate_tf_zgrid = np.ones((N_SYMS, 8), dtype = np.complex64)

    # downsample to 32 samples per symbol / 200 samples per sec
    df = SAMP_RATE / fft1_len
    fb_0 = int(0.5 + origin['f0'] / df )
    fb_top = int(0.5 + (origin['f0'] + 8.5*SYM_RATE) / df )
    fb_bot = int(0.5 + (origin['f0'] - 1.5*SYM_RATE) / df )

    candidate_spectrum[:(fb_top - fb_0)] = all_audio_spectrum[fb_0:fb_top]
    candidate_spectrum[-(fb_0-fb_bot):] = all_audio_spectrum[fb_bot:fb_0]
    candidate_zsig = np.fft.ifft(candidate_spectrum)

    # get candidate symbol spectra x79 with df = 1 tone spacing
    dt = (1 / SAMP_RATE) * fft1_len / fft2_len
    symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
    start = int(origin['t0']/dt)
    idx = start + np.arange(N_SYMS)*32
    idx = np.clip(idx, 0, len(candidate_zsig)-32)
    symbols = np.empty((N_SYMS,32), dtype=np.complex64)
    for j, i0 in enumerate(idx):
        symbols[j,:] = candidate_zsig[i0:i0+32]
    candidate_tf_zgrid = np.fft.fft(symbols, axis=1)[:, :8]

    return candidate_tf_zgrid


def gen_pulse(bt = 2.0):
    from scipy.special import erf
    samps_per_sym = int(SAMP_RATE / SYM_RATE)
    fchk = N_SYMS + samps_per_sym + bt + SAMP_RATE
    c = np.pi*np.sqrt(2.0/np.log(2.0))
    pulse = np.zeros(3*samps_per_sym)
    for i in range(3*samps_per_sym):
        tt = (i-1.5*samps_per_sym) / samps_per_sym
        pulse[i] = 0.5*(erf(c*bt*(tt+0.5))-erf(c*bt*(tt-0.5)))
    return pulse
pulse = gen_pulse()

def symbols_to_complex_audio(symbols, f_base = 100):
    samps_per_sym = int(SAMP_RATE / SYM_RATE)
    dphi_peak = 2.0*np.pi / samps_per_sym
    nsamps = int(samps_per_sym*(len(symbols)+2))
    dphi = np.zeros(nsamps)
    for isym, tone in enumerate(symbols):
        samp0 = isym * samps_per_sym
        t0 = isym * 0.16
        dphi[samp0: samp0 + len(pulse)] += dphi_peak * pulse * tone
    phi = np.add.accumulate(dphi) + 2*np.pi*f_base*np.arange(nsamps)/SAMP_RATE
    wf = np.exp(1j * (phi % (2*np.pi)))
    return wf

def _symbols_to_complex_audio(symbols, fs = SAMP_RATE, f_base=873.0, f_step=6.25):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    phase = 0
    waveform = []
    for s in symbols:
        f = f_base + s * f_step
        phase_inc = 2 * np.pi * f / fs
        w = np.exp(1j * (phase + phase_inc * np.arange(symbol_len)))
        waveform.append(w)
        phase = (phase + phase_inc * symbol_len) % (2 * np.pi)
    waveform = np.concatenate(waveform).astype(np.complex64)
    return waveform


origin_wanted = {'f0':1266.6, 't0':2.177, 'symbols':[int(s) for s in '3140652000000001123025577110543426103140652637173536360504202406550477433140652']}
origin_qrm = {'f0':1262.8, 't0':1.353, 'symbols':[int(s) for s in '3140652427540600505640165310555523223140652317130147565067602201255410233140652']}

target_samps_in = symbols_to_complex_audio(origin_wanted['symbols'], f_base = origin_wanted['f0'])
target_s0 = int(SAMP_RATE * origin_wanted['t0'])
target_samps = np.zeros(192000, dtype = np.complex64)
target_samps[target_s0:target_s0+len(target_samps_in)] = target_samps_in

qrm_samps = symbols_to_complex_audio(origin_qrm['symbols'], f_base = origin_qrm['f0'])
qrm_s0 = int(SAMP_RATE * (origin_qrm['t0'] - 0.16))

use_fake_composite = False
if use_fake_composite:
    combined_samps = target_samps.copy()
    combined_samps[qrm_s0:qrm_s0+len(qrm_samps)] += 5*qrm_samps
else:
    combined_samps_in = read_wav()
    combined_samps = np.zeros(192000)
    combined_samps[:len(combined_samps_in)] = combined_samps_in 

complex_amp = np.zeros(192000, dtype = np.complex64)
complex_amp[:len(qrm_samps)] = combined_samps[qrm_s0:qrm_s0+len(qrm_samps)] * np.conj(qrm_samps)

complex_amp = np.fft.fft(complex_amp)
nfilt = 20
window = np.cos(np.arange(0,np.pi/2,nfilt))**2
complex_amp[:nfilt] *= window/(np.sum(window)/len(window))
complex_amp[nfilt:] = 0
complex_amp = np.fft.ifft(complex_amp)

wanted_samps = combined_samps.copy()
wanted_samps[qrm_s0:qrm_s0+len(qrm_samps)] = combined_samps[qrm_s0:qrm_s0+len(qrm_samps)] - 2*np.real(complex_amp[:len(qrm_samps)] * qrm_samps)

target_spectrum = np.fft.fft(target_samps)
target_tfgrid = get_candidate_tfgrid(target_spectrum, origin_wanted)

combined_spectrum = np.fft.fft(combined_samps)
combined_tfgrid = get_candidate_tfgrid(combined_spectrum, origin_wanted)

wanted_spectrum = np.fft.fft(wanted_samps)
wanted_tfgrid = get_candidate_tfgrid(wanted_spectrum, origin_wanted)

target_dB = 20*np.log10(np.abs(target_tfgrid))
combined_dB = 20*np.log10(np.abs(combined_tfgrid))
wanted_dB = 20*np.log10(np.clip(np.abs(wanted_tfgrid), 0.001,None))



import matplotlib.pyplot as plt
fig, axs = plt.subplots(2,2, figsize = (8,8))
dBrange = 40
im = axs[0,0].imshow(combined_dB, origin = 'lower', vmax = np.max(combined_dB), vmin = np.max(combined_dB) - dBrange)
axs[0,0].set_title('Received signal')
im = axs[0,1].imshow(wanted_dB, origin = 'lower', vmax = np.max(wanted_dB), vmin = np.max(wanted_dB) - dBrange)
axs[0,1].set_title('Rx signal after subtraction')
im = axs[1,0].imshow(target_dB, origin = 'lower', vmax = np.max(target_dB), vmin = np.max(target_dB) - dBrange)
axs[1,0].set_title('Ideal signal CQ OR7EG JO11')
diff = target_dB - wanted_dB -np.max(target_dB) - np.max(wanted_dB)
im = axs[1,1].imshow(diff, origin = 'lower')
axs[1,1].set_title('dB diff between ideal and recovered')
print(np.sum(diff**2))

llr = dB_to_llr(wanted_dB[PAYLOAD_SYMB_IDXS,:])
res_osd = osd_012(llr, singleflips = 45, doubleflips = 25)
res_ldpc = ldpc_decode(llr, 900, 100)
print(f"{res_osd} {res_ldpc[0]}")

plt.show()

"""
WSJT-x decodes
usy/test_08      14.074 Rx FT8     16  1.0  763 UR7HN HB9BIN RR73
usy/test_08      14.074 Rx FT8     28  0.8 2046 CQ 9A9A JN75
usy/test_08      14.074 Rx FT8      3  1.3 2519 CQ F5CCX JN18
usy/test_08      14.074 Rx FT8      5  1.0  456 CQ ON2RK JO20
usy/test_08      14.074 Rx FT8    -18  1.3 1505 RX3ASQ TA3AHJ -08
usy/test_08      14.074 Rx FT8      2  0.7 2724 CQ R4HM LO43
usy/test_08      14.074 Rx FT8    -11  0.8 1062 CQ EA5OL IM99
usy/test_08      14.074 Rx FT8      8  0.8  394 M0XMX RV6AFG 73
usy/test_08      14.074 Rx FT8    -13  0.9 1264 SV2BRA I4WQH JN54
usy/test_08      14.074 Rx FT8     -6  0.8 1687 SQ6PZL MM0IMC -06
usy/test_08      14.074 Rx FT8    -16  1.7 1608 OZ5VO IT9HVZ JM78
usy/test_08      14.074 Rx FT8     -3  0.9  491 OK6LZ 2E0LDW +06
usy/test_08      14.074 Rx FT8    -13  1.4  265 CT3IQ EI8GVB IO63
usy/test_08      14.074 Rx FT8    -23  1.6 1267 CQ OR7EG JO11
usy/test_08      14.074 Rx FT8    -15  0.9  336 CQ JO1COV PM95
usy/test_08      14.074 Rx FT8    -24  0.8  987 RA3TPE TA1NGE RR73
usy/test_08      14.074 Rx FT8    -24  1.3 1927 RW6PA UA3NFG 73
usy/test_08      14.074 Rx FT8    -24  0.9 1368 SP9LKP F4VTS R-12
usy/test_08      14.074 Rx FT8    -17  1.2 2135 <...> LZ365BM RR73
"""


