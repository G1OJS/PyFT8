def get_bits(signal):
    graycode = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
    payload = signal.symbols[7:36] + signal.symbols[43:72]
    return [b for sym in payload for b in graycode[sym]]

def ldpc_check(codeword):
    from functools import reduce
    from operator import xor
    from src.Nm import Nm
    return all( reduce(xor, (codeword[i-1] for i in e if i != 0), 0) == 0 for e in Nm)

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
        return callsign if ' ' not in callsign.strip() else False

def unpack_ft8_g15(g15):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','R73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35 if r<=85 else r-35-101
    if(snr>50): return ''
    return f"{snr:02d}"

def FT8_decode(signals, ldpc = False):
    text = ''
    for signal in signals:
        bits = get_bits(signal)
        if(not ldpc_check(bits)):
            continue
        i3 = 4*bits[74]+2*bits[75]+bits[76]
        c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
        c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
        g15  = int(''.join(str(b) for b in bits[58:74]), 2)
        msg = f"{unpack_ft8_c28(c28_a)} {unpack_ft8_c28(c28_b)} {unpack_ft8_g15(g15)}"
        text += f"{signal.freq :6.1f} {signal.dt :6.2f} {i3} {signal.costas_score :6.2f} {msg} \n"
    return text



