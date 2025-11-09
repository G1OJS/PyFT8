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
    return call_a, call_b, grid_rpt

# ======================================================
# Main
# ======================================================

filename = '210703_133430.wav'
with wave.open(filename, 'rb') as wav:
    audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)

legit_calls = ['A92EE','DK8NE','DL5AXX','EA2BFM','EA3AGB','EA3BMU','EA3CJ','EA3GP','EA6EE','EA6VQ','F2VX','F5BZB','F5PSR','F5RXL','F6GCP','HA0DU','HA2NP','HA5WA','HA6FQ','HB9CQK','K1BZM','K1JT','KD2UGC','N1API','N1JFU','N1PJT','SV9CVY','W0RSJ','W1DIG','W1FC','WA2FZW','WM3PEN','XE2X']

t_oversamp = 3

FFT_len = 1920
nFreqs = int(1920/2) +1
hop_len = int(FFT_len / t_oversamp)
spec = np.zeros((nFreqs))
samp_idx = 0

while True:
    if(samp_idx + FFT_len > len(audio)): break
    specslice = np.fft.rfft(audio[samp_idx :samp_idx  + FFT_len] * np.kaiser(FFT_len,14))
    spec = np.vstack([spec, specslice])
    samp_idx  += hop_len
    
def decode(f0_idx = 345, t0_idx = 4):
    cspec = spec[t0_idx:t0_idx+79*t_oversamp, f0_idx:f0_idx+8]
    bits=[]
    gray_map_tuples = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
    gray_mask = np.array(gray_map_tuples, dtype=bool)
    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    for symb_idx in payload_symb_idxs:                         
        tp = np.abs(cspec[symb_idx*t_oversamp, :])**2
        tone = np.argmax(tp)
        bits.extend(gray_map_tuples[tone])
    call_a, call_b, grid_rpt = FT8_decode(bits)
    if (call_a in legit_calls or call_b in legit_calls): 
        print(f"{f0_idx} {t0_idx} {call_a} {call_b} {grid_rpt}")

for f_idx in range(nFreqs-8):
    for t_idx in range(44):
        decode(f0_idx = f_idx, t0_idx = t_idx)

#import matplotlib.pyplot as plt
#fig, ax = plt.subplots()
#ax.imshow(np.abs(cspec))
#plt.show()



