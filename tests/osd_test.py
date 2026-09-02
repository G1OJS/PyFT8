import numpy as np
import wave
from PyFT8.decoders import crc_unpack91
import time

import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)


#============== OSD ===========================================================
generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G0 = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)

def enc(u, G):
    cw = np.zeros(174, dtype = np.uint8)
    for i in range(91):
        if u[i]:
            cw = cw ^ G[i,:]
    return cw

def osd_ref(llr):
    G = G0.copy()
    rowperm = np.arange(91)
    colperm = np.argsort(-np.abs(llr))
    curr_row = 0
    for curr_col in range(174):
        ones_below = np.where(G[rowperm[curr_row:], colperm[curr_col]] == 1)[0]
        if ones_below.size > 0:
            swap_row = curr_row + ones_below[0]
            rowperm[[curr_row, swap_row]] = rowperm[[swap_row, curr_row]]
            r_curr = rowperm[curr_row]
            c_curr = colperm[curr_col]
            g_c_curr = G[:, c_curr].copy()
            g_c_curr[r_curr] = 0
            rows_to_xor = np.where(g_c_curr == 1)[0]
            G[rows_to_xor, :] ^= G[r_curr, :]
            colperm[[curr_row, curr_col]] = colperm[[curr_col, curr_row]]  
            curr_row += 1
            if curr_row > 90:
                break
          
    chbits174 = (llr>0).astype(np.uint8)
    chbits91 = chbits174[colperm][:91]
    chbits91[rowperm] = chbits91
    chvals174 = np.abs(llr)

    
    cw174 = ((chbits91 @ G) & 1)
    msg_tuple, bits77_int = crc_unpack91(cw174[:91])
    if msg_tuple:
        return msg_tuple, bits77_int, 0

    fliplist = list(rowperm[::-1])
    current_best_distance = 1e20
    
    cw_out91 = []
    for i in range(91):
        for j in range(-1, i):
            bits = chbits91.copy()
            bits[fliplist[i]] ^= 1
            if j>=0:
                bits[fliplist[j]] ^= 1
            cw174 = ((bits @ G) & 1)
            distance = np.sum(chvals174 * np.bitwise_xor(cw174.astype(np.uint8),chbits174))
            if distance < current_best_distance:
                cw_out91 = cw174[:91]
                current_best_distance = distance
    if any(cw_out91):
        msg_tuple, bits77_int = crc_unpack91(cw_out91)
        if msg_tuple:
            return msg_tuple, bits77_int, 1
    
    return None, None, -1
 
def osd(llr):
    G = G0.copy()
    chbits174 = (llr>0).astype(np.uint16)

    chvals174 = np.abs(llr)
    chvals174 = chvals174 / np.max(chvals174)    
    chvals174 = np.array([int(v*256) for v in chvals174]).astype(np.uint16)

    colperm = np.argsort(chvals174).astype(np.uint8)[::-1]
    rowperm = np.arange(91).astype(np.uint8)
    curr_row = 0
    for curr_col in range(174):
        ones_below = np.where(G[rowperm[curr_row:], colperm[curr_col]] == 1)[0]
        if ones_below.size > 0:
            swap_row = curr_row + ones_below[0]
            rowperm[[curr_row, swap_row]] = rowperm[[swap_row, curr_row]]
            r_curr = rowperm[curr_row]
            c_curr = colperm[curr_col]
            g_c_curr = G[:, c_curr].copy()
            g_c_curr[r_curr] = 0
            rows_to_xor = np.where(g_c_curr == 1)[0]
            G[rows_to_xor, :] ^= G[r_curr, :]
            colperm[[curr_row, curr_col]] = colperm[[curr_col, curr_row]]  
            curr_row += 1
            if curr_row > 90:
                break

    chbits91 = chbits174[colperm][:91].astype(np.uint8)
    chbits91[rowperm] = chbits91

    cw174 = ((chbits91 @ G) & 1)
    msg_tuple, bits77_int = crc_unpack91(cw174[:91])
    if msg_tuple:
        return msg_tuple, bits77_int, 0

    parbits_idx = colperm[91:][:25]
    Gp = G[:, parbits_idx].astype(np.uint8)
    chbits_par = chbits174[parbits_idx].astype(np.uint8)

    cw_out91 = None
    jj_min = 80
    current_best_distance = 1e20
    for ii in range(-1, 91):
        jjmin = ii if ii > jj_min else jj_min
        for jj in range(jjmin, 91):
            pb = Gp[jj,:]
            bits = chbits91.copy()
            if ii >= 0:
                bits[ii] ^= 1
            if jj != ii and ii >= 0:
                bits[jj] ^= 1
            pe = np.bitwise_xor(chbits_par, pb)
            if pe.sum() <= 8:                
                cw174 = ((bits @ G) & 1)
                distance = np.dot(chvals174, np.bitwise_xor(cw174, chbits174))
                if distance < current_best_distance:
                    cw_out91 = cw174[:91]
                    current_best_distance = distance

    if not cw_out91 is None:
        msg_tuple, bits77_int = crc_unpack91(cw_out91)
        if msg_tuple:
            return msg_tuple, bits77_int, 1
    
    return None, None, -1



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

for origin in [{'f0':1505, 't0':1.3 + 0.5}, {'f0':1262, 't0':0.9 + 0.5}, {'f0':763, 't0':1.0 + 0.5}]:
    candidate_tf_zgrid = get_candidate_tfgrid(all_audio_spectrum, origin)
    dB = np.log10(np.abs(candidate_tf_zgrid))
    llr = dB_to_llr(dB[PAYLOAD_SYMB_IDXS,:])

    print('')
    
    t = time.time()
    res_osd = osd_ref(llr)
    print(f"Ref:  {time.time()-t:7.3f} {res_osd[0]}")

    t = time.time()
    res_osd = osd(llr)
    print(f"Test: {time.time()-t:7.3f} {res_osd[0]}")


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


