import numpy as np
import wave
from PyFT8.decoders import ldpc_decode, osd, crc_unpack91
import time

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

SAMP_RATE = 12000
SYM_RATE = 6.25
N_SYMS = 79
T_CYC = 15
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))
I512 = np.arange(512)
BIT_IS_1 = np.array([((I512 >> (8-b)) & 1) == 1 for b in range(9)])
BIT_IS_0 = ~BIT_IS_1
I0 = I512 // 64
I1 = (I512 & 63) // 8
I2 = I512 & 7
    
def _z_to_llr(z):
    p = np.abs(z[PAYLOAD_SYMB_IDXS, :])**2
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc)).ravel()
    return np.array(llr)

def _z_to_llr_3(z):
   # t = time.time()
    llr = np.zeros(174)
    GRAY = [0,1,3,2,5,6,4,7]
    zg = z[:,GRAY]
    for payload_block in range(2):
        for sym_rel_idx in range(0,29,3):
            sym_abs_idx = sym_rel_idx + [7, 43][payload_block]
            z3 = zg[sym_abs_idx, I0] + zg[sym_abs_idx + 1, I1] + zg[sym_abs_idx +2, I2]
            s512 = np.abs(z3)**2
            bg = sym_rel_idx * 3 + 87 * payload_block
            #print(sym_rel_idx, sym_abs_idx, bg, bg + 9)
            for b in range(9):
                if bg + b < 174:
                    llr[bg + b] = np.max(s512[BIT_IS_1[b]]) - np.max(s512[BIT_IS_0[b]])
  #  print(time.time() - t)
    return llr
  

def scale_llr(llr):
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
        if 0 <= i0 <= 2812:
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
#origin = {'f0':763, 't0':1.0 + 0.5, 'msg':'UR7HN HB9BIN RR73'}
#origin = {'f0':1267, 't0':1.6 + 0.5, 'msg':'CQ OR7EG JO11'}
#origin = {'f0':1927, 't0':1.3 + 0.5, 'msg':'RW6PA UA3NFG 73'}
#origin = {'f0':0, 't0':0 + 0.5, 'msg':'ZL2OK PD1PDR JO21'}
#origin = {'f0':0, 't0':0 + 0.5, 'msg':'DL1KDA R3FO R-09'}
#origin = {'f0':1561, 't0':0.8 + 0.5, 'msg':'CQ 7Z1AL LL56'}
origin = {'f0':773, 't0':0.9 + 0.5, 'msg':'CQ DM100ZM',
          'llr-ftn-subon':[ -0.247141808,  0.247201607, -0.247380987, -0.251542151,  0.251542151, -0.250205517,  0.357100338, -0.364282578,  0.345920771,  0.229561791,  0.229758218,  0.229758218, -0.108405016, -0.108405016, -0.108405016,  -8.11156929E-02, -7.11510330E-02, -9.13958773E-02, -4.25714105E-02, -4.25714105E-02, -7.83516765E-02, -6.52027354E-02, -7.00134933E-02, -7.39185065E-02, -9.37251002E-02, -9.37251002E-02 -0.103364162, -0.183202699, -0.183202699, -0.223886937, -0.150592506, -0.176336810, -0.178865209, -0.412790358,  0.412790358, -0.412790358,   4.34636176E-02,  -3.75429802E-02,   8.16944055E-03, -0.116687618,  0.116687618,  0.195356667,  0.115234591,   8.00968707E-02 -0.113928527,  0.263238460, -0.269241422,  0.263238460,  0.134238824, -0.103951201, -0.167443484,  0.188967869, -0.178186998,  0.178186998,  0.221902117, -0.221902117,  0.232294112, -0.137700438,  0.135116279, -0.137700438,  0.104262970,   2.47699153E-02,   2.47699153E-02,  -1.33829555E-02,   4.36921678E-02, -1.33829555E-02,  0.169266298, -0.169266298,  0.172230750,   6.03659675E-02,   1.74090173E-02, -6.75273240E-02, -1.33730583E-02,  1.33730583E-02,  2.17816122E-02, -3.19722854E-02, -5.51123433E-02, -3.19722854E-02, -5.18188924E-02, -4.64974456E-02, -5.74114062E-02 -0.110999003,  0.116876699, -0.117678858,   2.50795446E-02, -5.71228229E-02, -2.87288278E-02 -0.273311853,  0.263777196,  0.278858751, -0.568686485,  0.568532944, -0.568686485, -0.708780169,  0.702362299,  0.699598372, -0.824658871, -0.840433717, -0.840433717,  -1.08767784,  -1.08767784,   1.08767784,   1.87456656,   1.76393151,   1.87456656,  -1.79098141,  -1.98100913,  -1.97973228,   2.95663738,  -2.94883561,   2.95663738, -0.995571136,   1.22829890,  -1.22829890,  -2.98609304,   2.93565202,  -2.90221572,  -3.60981894,   3.60590959,   3.58560562,   3.77504253,  -3.77504253,  -3.78852725,  -3.31214881,  -3.20894599,  -3.20894599,   2.49681783,   2.54629803,  -2.61163473, -0.488757908,  0.473341495,  0.480483413,  -2.29472756,   2.29472756,   2.24786592,   3.78822041,  -3.78822041,  -3.78822041,  0.831111968, -0.763662279, -0.682382822,   4.38434601,  -4.29693317,   4.24929667,   4.96497154,   4.96497154,   4.97503710,  -3.73947835,   3.73947835,  -3.79446912,   5.77410460,   5.77210808,   5.69561148,  -4.67639637,   4.66955042,  -4.66955042,  -5.75506830,  -6.05437374,  -6.02603340,   6.63667154,  -6.47657156,   6.58709478,  -7.11511135,   7.11511135,  -7.26343727,  -4.48871517,  -4.48871517,  -4.48871517,  -7.38202190,   7.38202190,   7.38202190,   7.35957336,  -7.41711426,  -7.35957336  ]}

ax.plot(origin['llr'], label = 'ftn')

candidate_tf_zgrid = get_candidate_tfgrid(all_audio_spectrum, origin)
llr = _z_to_llr(candidate_tf_zgrid)
llr = scale_llr(llr)
#print(', '.join([f"{v}" for v in llr]))
ax.plot(llr, label = 'py-1sym')
res_osd = osd(llr)
res_ldpc = ldpc_decode(llr, 900, 100)
print(f"{res_osd[0]} {res_ldpc[0]}")

llr = _z_to_llr_3(candidate_tf_zgrid)
llr = scale_llr(llr)
#print(', '.join([f"{v}" for v in llr]))
ax.plot(llr, label = 'py-3sym')
res_osd = osd(llr)
res_ldpc = ldpc_decode(llr, 900, 100)

print(f"{res_osd[0]} {res_ldpc[0]}")

#dB = 20*np.log10(np.abs(candidate_tf_zgrid))
#dB = np.clip(dB, np.max(dB)-30, None)

#im = ax.imshow(dB, origin = 'lower')
#im.set_data(dB)

plt.legend()
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


