import re
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
import numpy as np
from itertools import islice
from PyFT8.FT8_constants import kCRC_BITS, kCRC_POLY, kMSG_BITS, kGRAY_MAP, kCOSTAS, kGEN
import PyFT8.FT8_global_helpers as ghlp

def pack_ft8_c28(call):
    from string import ascii_uppercase as ltrs, digits as digs
    m = int(re.search(r"\d", call).start())
    call = np.array(['',' ','',''])[m] + call
    charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
    factors = np.array([36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1])
    indices = np.array([cmap.index(call[i]) for i, cmap in enumerate(charmap)])
    return np.sum(factors * indices) + 2_063_592 + 4_194_304

def pack_ft8_g15(txt):
    # 'RR73', '-9', 'R-9', 'RRR' not sure ...
    if txt.startswith('-'):
        n = int(txt[1:])
        return 32400 + 11 + n - 1 
    if txt.startswith('R-'):
        n = int(txt[2:])
        return 32400 + n + 1 - 1 
    if txt == 'RR73':
        return 32400
    if txt == 'RRR':
        return 32401
    v = (ord(txt[0].upper()) - 65)
    v = v * 18 + (ord(txt[1].upper()) - 65)
    v = v * 10 + int(txt[2])
    v = v * 10 + int(txt[3])
    return v

def reverse_Bits(n, no_of_bits):
    result = 0
    for i in range(no_of_bits):
        result <<= 1
        result |= n & 1
        n >>= 1
    return result

def ldpc_encode(msg_crc: int) -> int:
    msg_crc = int(msg_crc)
    parity_bits = 0
    print(f"{msg_crc:0100b}")
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits, parity_bits

def gray_encode(bits: int) -> list[int]:
    syms = []
    for _ in range(174 // 3):
        chunk = bits & 0x7
        syms.insert(0, kGRAY_MAP[chunk])

        bits >>= 3
    return syms

def add_kCOSTAS(syms: list[int]) -> list[int]:
    return kCOSTAS + syms[:29] + kCOSTAS + syms[29:] + kCOSTAS

def encode_bits77(bits77_int):
    bits91_int, bits14_int = ghlp.append_crc(bits77_int)
    bits174_int, bits83_int = ldpc_encode(bits91_int)
    syms = gray_encode(bits174_int)
    symbols = add_kCOSTAS(syms)
    return symbols, bits174_int, bits91_int, bits14_int, bits83_int




