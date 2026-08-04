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
    fft1_len = len(all_audio_spectrum)
    global candidate_spectrum, candidate_tf_zgrid

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

fft2_len = 3200
candidate_spectrum = np.zeros(fft2_len, dtype = np.complex64)
candidate_tf_zgrid = np.ones((N_SYMS, 8), dtype = np.complex64)
wav_file = 'test_08.wav'
# get full audio spectrum 
wf = wave.open(wav_file, "rb")
all_audio_frames = wf.readframes(SAMP_RATE * T_CYC)
wf.close()
fft1_len = 192000
samples = np.zeros(fft1_len)
samps_in = np.frombuffer(all_audio_frames, dtype=np.int16).astype(np.float32)
samples[:len(samps_in)] = samps_in 
all_audio_spectrum = np.fft.fft(samples)

import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize = (12,5))
origin = {'f0':1266.5, 't0':1.6 + 0.5}
#origin = {'f0':1262, 't0':0.9 + 0.5}

im = None
for f in np.linspace(1266.65, 1266.68, 10):
    for t in np.linspace(2.17, 2.19, 10):
        origin = {'f0':f, 't0':t}

        candidate_tf_zgrid = get_candidate_tfgrid(all_audio_spectrum, origin)
        dB = np.log10(np.abs(candidate_tf_zgrid))
        llr = dB_to_llr(dB[PAYLOAD_SYMB_IDXS,:])
        res_osd = osd_012(llr, singleflips = 45, doubleflips = 25)
        res_ldpc = ldpc_decode(llr, 900, 100)
        print(f"{f:7.3f} {t:7.3f} {res_osd} {res_ldpc[0]}")

        dB = np.clip(dB, np.max(dB)-30, None)
        if im is None:
            im = ax.imshow(dB, origin = 'lower')
        im.set_data(dB)
        plt.pause(0.01)

#plt.show()



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


