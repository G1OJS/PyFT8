from src.FT8_decoder import unpack_ft8_c28, unpack_ft8_g15
from string import ascii_uppercase as ltrs, digits as digs

def pack_ft8_c28(callsign):
    c = callsign.ljust(6)  # pad to 6 chars
    charmap = [' ' + digs + ltrs, digs + ltrs, digs] + [' ' + ltrs] * 3
    divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
    n = 0
    for d, t, ch in zip(divisors, charmap, c):
        i = t.index(ch)
        n += i * d
    n += (2063592+4194304)
    return n

def pack_ft8_g15(txt):
    if txt.startswith('-'):
        n = int(txt[1:])
        return 32400 + 11 + n - 1  # matches unpack mapping: 32413..32423 = -01..-11
    if txt.startswith('R-'):
        n = int(txt[2:])
        return 32400 + n + 1 - 1   # 32402..32412 = R-01..R-11
    if txt == 'RR73':
        return 32400
    if txt == 'RRR':
        return 32401

    v = (ord(txt[0].upper()) - 65)
    v = v * 18 + (ord(txt[1].upper()) - 65)
    v = v * 10 + int(txt[2])
    v = v * 10 + int(txt[3])

    return v


calltests = ['WM3PEN']
for c in calltests:
    c28 = pack_ft8_c28(c)
    print(unpack_ft8_c28(c28))

gridtests = ['RR73', '-9', 'R-9', 'IO90', 'RR99']
for g in gridtests:
    g15 = pack_ft8_g15(g)
    print(unpack_ft8_g15(g15))
