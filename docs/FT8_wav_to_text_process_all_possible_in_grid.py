import wave
import numpy as np

# ======================================================
# FT8 Unpacking functions
# ======================================================
def unpack_ft8_c28(c28):
    from string import ascii_uppercase as ltrs, digits as digs
    if c28<3: return ["DE", 'QRZ','CQ'][c28]
    n = c28 - 2_063_592 - 4_194_304 # NTOKENS, MAX22
    if n >= 0:
        charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
        divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
        indices = []
        for d in divisors:
            i, n = divmod(n, d)
            indices.append(i)
        callsign = ''.join(t[i] for t, i in zip(charmap, indices)).lstrip()
        return callsign.strip()
    return '<...>'

def unpack_ft8_g15(g15, ir):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    R = '' if (ir == 0) else 'R'
    return f"{R}{snr:+03d}"

def FT8_decode(bits):
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
    c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
    ir = int(bits[58])
    g15  = int(''.join(str(b) for b in bits[59:74]), 2)
    if(c28_a + c28_b + g15 == 0):
        return
    call_a = unpack_ft8_c28(c28_a)
    call_b =  unpack_ft8_c28(c28_b)
    grid_rpt = unpack_ft8_g15(g15, ir)
    return f"{call_a} {call_b} {grid_rpt}"

# ======================================================
# Main
# ======================================================

filename = '210703_133430.wav'
with wave.open(filename, 'rb') as wav:
    audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)

legit_msgs = ['KD2UGC F6GCP R-23',  'WA2FZW DL5AXX RR73',  'W1FC F5BZB -08',
              'CQ DL8YHR JO41',  'W1DIG SV9CVY -14',  'CQ EA2BFM IN83',
              'N1JFU EA6EE R-07',  'N1PJT HB9CQK -10',  'N1API HA6FQ -23',
              'A92EE F5PSR -14',  'K1BZM EA3GP -09',  'K1JT HA0DU KN07',
              'WM3PEN EA6VQ -09',  'XE2X HA2NP RR73',  'K1JT EA3AGB -15',
              'K1BZM DK8NE -10',  'W0RSJ EA3BMU RR73',  'K1BZM EA3CJ JN01',
              'N1API F2VX 73',  'K1JT HA5WA 73',  'CQ F5RXL IN94']

t_oversamp = 3
f_oversamp = 5
FFT_len = 1920 * f_oversamp
nFreqs = int(FFT_len/2) +1
hop_len = int(FFT_len / (t_oversamp*f_oversamp))

max_freq_idx = int(nFreqs/2)


spec = np.zeros((nFreqs))
samp_idx = 0
while True:
    if(samp_idx + FFT_len > len(audio)): break
    specslice = np.fft.rfft(audio[samp_idx :samp_idx  + FFT_len] * np.kaiser(FFT_len,14))
    spec = np.vstack([spec, specslice])
    samp_idx  += hop_len

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
fig, ax = plt.subplots()
ax.imshow(np.abs(spec[:,:max_freq_idx]), norm=LogNorm())
plt.show()


def decode(f0_idx = 345, t0_idx = 4):
    cspec = spec[t0_idx:t0_idx+79*t_oversamp, f0_idx:f0_idx + 8*f_oversamp]
    bits=[]
    gray_map_tuples = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
    gray_mask = np.array(gray_map_tuples, dtype=bool)
    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    for symb_idx in payload_symb_idxs:                         
        tp = np.abs(cspec[symb_idx*t_oversamp, :])**2
        tone = int(np.argmax(tp) / f_oversamp)
        bits.extend(gray_map_tuples[tone])
    print(''.join([str(b) for b in bits]))
    msg = FT8_decode(bits)
    if (msg in legit_msgs):
        return(msg)

msg = decode()

"""
decodes = set()
for f_idx in range(max_freq_idx):
    for t_idx in range(44):
        msg = decode(f0_idx = f_idx, t0_idx = t_idx)
        if(msg):
            print(f"{f_idx} {t_idx} {msg}")
            decodes.add(msg)
print(f"{len(decodes)} messages of {len(legit_msgs)}")
"""




