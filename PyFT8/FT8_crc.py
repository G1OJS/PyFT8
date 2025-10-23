import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
import numpy as np
from PyFT8.FT8_constants import kCRC_BITS, kCRC_POLY, kMSG_BITS
# kCRC_BITS, kCRC_POLY, kMSG_BITS are not used below but need to be when making this generic

def crc14(bits77_int: int) -> int:
    # Generator polynomial (0x2757), width 14, init=0, refin=false, refout=false
    poly = 0x2757
    width = 14
    mask = (1 << width) - 1
    # Pad to 96 bits (77 + 14 + 5)
    nbits = 96
    reg_int = 0
    for i in range(nbits):
        # bits77 is expected MSB-first (bit 76 first)
        inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
        bit14 = (reg_int >> (width - 1)) & 1
        reg_int = ((reg_int << 1) & mask) | inbit
        if bit14:
            reg_int ^= poly
    return reg_int

def BElst_to_int(bits_BElst):
    """bits is LSB-first: sum(bits[i] << i)."""
    n = 0
    for i, b in enumerate(bits_BElst):
        n |= (int(b) & 1) << i
    return n

def int_to_BElst(n, width):
    """Return [b0, b1, ..., b(width-1)] where b0 is LSB of n."""
    bits_BElst = [(n >> i) & 1 for i in range(width)]
    return bits_BElst

def check_crc(bits91_BElst):
    """Return True if the 91-bit message (77 data + 14 CRC) passes WSJT-X CRC-14."""
    msg_bits_LElst = bits91_BElst[0:77][::-1]
    crc_bits_LElst = bits91_BElst[77:91][::-1]  
    new_crc_LElst = int_to_BElst(crc14(BElst_to_int(msg_bits_LElst)),14)
    return np.array_equal(new_crc_LElst, crc_bits_LElst)

def append_crc(bits77_int):
    """Append 14-bit WSJT-X CRC to a 77-bit message, returning a 91-bit list."""
    bits14_int = crc14(bits77_int)
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

