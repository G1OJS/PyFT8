import numpy as np
from PyFT8.decoders import ldpc_decode, osd_012, crc_unpack91
from PyFT8.transmitter import symbols_to_complex_audio
import matplotlib.pyplot as plt

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

SAMP_RATE = 12000
SYM_RATE = 6.25
N_SYMS = 79
T_CYC = 15
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))

def read_wav(wav_file = 'test_08.wav'):
    import wave
    wf = wave.open(wav_file, "rb")
    all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
    samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
    wf.close()
    return samps_in

def plot_grid(ax, audio_buffer, frng, title,  vmin, vmax):
    hps, bpt = 1, 1
    hpc = int(hps * SYM_RATE * 15)
    grid_fft_len = int(bpt * SAMP_RATE / SYM_RATE)
    samps_per_hop = int(SAMP_RATE / (SYM_RATE * hps) )
    grid = np.zeros((hpc, grid_fft_len))
    df = SAMP_RATE / grid_fft_len
    h0 = int(grid_fft_len / samps_per_hop)
    fft_in = np.zeros(grid_fft_len)
    search_fft_window = np.hanning(grid_fft_len).astype(np.float32)
    for h in range(1, hpc):
        sn = h * samps_per_hop
        sn = sn if sn < len(audio_buffer) else len(audio_buffer)
        s0 = sn - grid_fft_len
        s0 = s0 if s0 > 0 else 0
        fft_in [:sn-s0] = audio_buffer[s0: sn]
        grid[h,:] = np.abs(np.fft.fft(fft_in * search_fft_window))
    dB_grid = -53.4 + 20.0*np.log10(grid + 1e-12)
    if0 = int(frng[0] / df)
    if1 = int(frng[1] / df)
    vals = dB_grid[:, if0:if1]
    trng = len(audio_buffer) / SAMP_RATE
    im1 = ax.imshow(vals, vmax = vmax, vmin = vmin, origin = 'lower',
                    extent = [frng[0], frng[1], 0, trng], aspect = 'auto')
    ax.set_title(f"{title} max = {np.max(vals):6.1f}")
    return grid

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
    fb_0 = int(0.5 + origin['fHz'] / df )
    fb_top = int(0.5 + (origin['fHz'] + 8.5*SYM_RATE) / df )
    fb_bot = int(0.5 + (origin['fHz'] - 1.5*SYM_RATE) / df )

    candidate_spectrum[:(fb_top - fb_0)] = all_audio_spectrum[fb_0:fb_top]
    candidate_spectrum[-(fb_0-fb_bot):] = all_audio_spectrum[fb_bot:fb_0]
    candidate_zsig = np.fft.ifft(candidate_spectrum)

    # get candidate symbol spectra x79 with df = 1 tone spacing
    dt = (1 / SAMP_RATE) * fft1_len / fft2_len
    symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
    start = int(origin['tsec']/dt)
    idx = start + np.arange(N_SYMS)*32
    idx = np.clip(idx, 0, len(candidate_zsig)-32)
    symbols = np.empty((N_SYMS,32), dtype=np.complex64)
    for j, i0 in enumerate(idx):
        symbols[j,:] = candidate_zsig[i0:i0+32]
    candidate_tf_zgrid = np.fft.fft(symbols, axis=1)[:, :8]

    return candidate_tf_zgrid

def place_in_buffer(data, n, len_buffer):
    buffer = np.zeros(len_buffer, dtype = data.dtype)
    n = n if n > 0 else 0
    buffer[n:n+len(data)] = data
    return buffer


def recover_and_decode(audio_received, decoded_fHz, decoded_tsec):
    nfft = 192000 
    ex = place_in_buffer(audio_received, 0, nfft)
    sig_audio = symbols_to_complex_audio(origin_qrm['symbols'], f_base = decoded_fHz)
    sig_audio = place_in_buffer(sig_audio, int(SAMP_RATE * decoded_tsec), nfft)

    window = np.cos(np.linspace(0, np.pi/2, subtraction_filterlen))**2
    subtraction_window = np.zeros(nfft)
    subtraction_window[:subtraction_filterlen] = window
    subtraction_window[-subtraction_filterlen:] = window[::-1]
    subtraction_window /= np.sum(subtraction_window)
    filt = np.fft.fft(subtraction_window)
    
    amp = ex * np.conj(sig_audio)
    amp = np.fft.fft(amp)
    amp *= filt
    amp = np.fft.ifft(amp)
    amp = place_in_buffer(amp, 0, nfft)
    sub = 2*np.real(amp * sig_audio)
    audio_recovered = ex.real - sub

    audio_buff = np.zeros(192000)
    audio_buff[:len(audio_recovered)] = audio_recovered
    audio_spectrum = np.fft.fft(audio_buff)
    grid = get_candidate_tfgrid(audio_spectrum, origin_wanted)
    grid_dB = 20*np.log10(np.abs(grid))
    llr = dB_to_llr(grid_dB[PAYLOAD_SYMB_IDXS,:])
    res_osd = osd_012(llr, singleflips = 45, doubleflips = 25)
    res_ldpc = ldpc_decode(llr, 900, 100)
    print(f"{res_osd} {res_ldpc[0]}")
    return sig_audio, amp, audio_recovered, sub
#==================================================================================================

origin_wanted = {'lev': 0, 'fHz':1268.78, 'tsec':2.1, 'symbols':[int(s) for s in '3140652000000001123025577110543426103140652637173536360504202406550477433140652']}
origin_qrm = {'lev':6, 'fHz':1263.875, 'tsec':0.43, 'symbols':[int(s) for s in '3140652427540600505640165310555523223140652317130147565067602201255410233140652']}
subtraction_filterlen = 2000
#t_offset_real = -0.0193
#f_offset_real = -0.8
t_offset_real = 0
f_offset_real = 0

audio_wanted = np.imag(symbols_to_complex_audio(origin_wanted['symbols'], f_base = origin_wanted['fHz']))
audio_wanted = audio_wanted * 10**(origin_wanted['lev']/20)
audio_wanted = place_in_buffer(audio_wanted, int(SAMP_RATE * origin_wanted['tsec']) , 192000)

audio_qrm = np.imag(symbols_to_complex_audio(origin_qrm['symbols'], f_base = origin_qrm['fHz']))
audio_qrm = audio_qrm * 10**(origin_qrm['lev']/20) 
audio_qrm = place_in_buffer(audio_qrm, int(SAMP_RATE * origin_qrm['tsec']) , 192000)

#====================================================================================================
audio_expected = audio_wanted + audio_qrm
audio_received = np.zeros_like(audio_wanted)
audio_in = read_wav() * 10**(-41/20)
audio_in = place_in_buffer(audio_in, int(-0.9 * SAMP_RATE), 192000)
audio_received = audio_in[:len(audio_received)]

#====================================================================================================
frng = [1100, 1600]
frng[0] = frng[0] if frng[0] >= 0 else 0
fig, axs = plt.subplots(3,4, figsize = (10,10))

grid_wanted = plot_grid(axs[0, 0], audio_wanted, frng, "Signal", -40, 6)
grid_qrm = plot_grid(axs[0, 1], audio_qrm, frng, "QRM", -40, 6)
grid_expected = plot_grid(axs[0, 2], audio_expected, frng, "Signal expected", -40, 6) 
grid_received = plot_grid(axs[0, 3], audio_received, frng, "Signal received", -40, 6)

#====================================================================================================
decoded_fHz, decoded_tsec = origin_qrm['fHz'], origin_qrm['tsec']
sig_audio, amp_synth, audio_recovered_synth, sub_synth = recover_and_decode(audio_expected, decoded_fHz, decoded_tsec)
sig_audio, amp_real, audio_recovered_real, sub_real = recover_and_decode(audio_received, decoded_fHz + f_offset_real, decoded_tsec + t_offset_real)

plot_grid(axs[1, 0], np.real(sig_audio), frng, "Re(ref sig)", -40, 6)
plot_grid(axs[1, 1], np.real(amp_synth), [0,200], "Re(Camp)(syn)", -40, 0)
plot_grid(axs[1, 2], sub_synth, frng, "RecovQRM(syn)", -40, 6)
plot_grid(axs[1, 3], audio_recovered_synth, frng, "RecovSig(syn)", -40, 6)

plot_grid(axs[2, 0], np.real(sig_audio), frng, "Re(ref sig)", -40, 6)
plot_grid(axs[2, 1], np.real(amp_real), [0,200], "Re(Camp)(real)", -40, 0)
plot_grid(axs[2, 2], sub_real, frng, "RecovQRM(real)", -50, -4)
plot_grid(axs[2, 3], audio_recovered_real, frng, "RecovSig(real)", -40, 6)


print("Synth CORR:", np.corrcoef(sub_synth, audio_qrm)[0,1])
print("Real  CORR:", np.corrcoef(sub_real, audio_qrm)[0,1])




plt.tight_layout()
plt.show()

