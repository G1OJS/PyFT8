import re
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
import numpy as np
from itertools import islice
from PyFT8.FT8_constants import kCRC_BITS, kCRC_POLY, kMSG_BITS, kGRAY_MAP, kCOSTAS, kGEN

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


def parity(x: int) -> int:
    return bin(x).count('1') & 1

def crc14(msg: int) -> int:
    poly = kCRC_POLY
    reg = 0
    for i in range(kMSG_BITS):
        bit = ((msg >> (kMSG_BITS - 1 - i)) & 1) ^ ((reg >> 13) & 1)
        reg = ((reg << 1) & 0x3fff)
        if bit:
            reg ^= poly
    return reg

def ldpc_encode(msg_crc: int) -> int:
    # enforce Python ints
    msg_crc = int(msg_crc)
    parity_bits = 0
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits

def gray_encode(bits: int) -> list[int]:
    syms = []
    for _ in range(174 // 3):
        chunk = bits & 0x7
        syms.insert(0, kGRAY_MAP[chunk])
        bits >>= 3
    return syms

def add_kCOSTAS(syms: list[int]) -> list[int]:
    return kCOSTAS + syms[:29] + kCOSTAS + syms[29:] + kCOSTAS

def encode_bits77(bits77):
    msg_crc = (bits77 << 14) | crc14(bits77)
    bits174 = ldpc_encode(msg_crc)
    syms = gray_encode(bits174)
    symbols = add_kCOSTAS(syms)
    return symbols
