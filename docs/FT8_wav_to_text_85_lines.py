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
    message = f"{call_a} {call_b} {grid_rpt}"
    return message

# ======================================================
# Main
# ======================================================

filename = '210703_133430.wav'
with wave.open(filename, 'rb') as wav:
    audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    
nFFT = 1920
spec = np.zeros((int(nFFT/2)+1))
samp_idx = 0

while True:
    if(samp_idx +nFFT > len(audio)): break
    specslice = np.fft.rfft(audio[samp_idx :samp_idx  + nFFT] * np.kaiser(nFFT,14))
    spec = np.vstack([spec, specslice])
    samp_idx  += nFFT
    
f0_idx = 345            # magic number locating the signal frequency
t0_idx =  4              # magic number locating the signal start time

cspec = spec[t0_idx:t0_idx+79, f0_idx:f0_idx+8]
bits=[]
gray_map_tuples = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
gray_mask = np.array(gray_map_tuples, dtype=bool)
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
for symb_idx in payload_symb_idxs:                         
    tp = np.abs(cspec[symb_idx, :])**2
    tone = np.argmax(tp)
    bits.extend(gray_map_tuples[tone])
decode = FT8_decode(bits)
print(decode)

import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.imshow(np.abs(cspec))
plt.show()



