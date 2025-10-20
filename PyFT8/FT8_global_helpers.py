import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
import numpy as np
from PyFT8.FT8_constants import kCRC_BITS, kCRC_POLY, kMSG_BITS

# --------------------------
# Conversions
# --------------------------

# ---- LSB-first conversions (FT8/WSJT-X convention) ----

def bits_to_int(bits):
    """bits is LSB-first: sum(bits[i] << i)."""
    n = 0
    for i, b in enumerate(bits):
        n |= (int(b) & 1) << i
    return n

def int_to_bits(n, width):
    """Return [b0, b1, ..., b(width-1)] where b0 is LSB of n."""
    return [(n >> i) & 1 for i in range(width)]

def bits_to_str(bits):
    """Return a string of '0' and '1' characters from bits."""
    return ''.join(str(int(b)) for b in bits)

def str_to_bits(s):
    """Convert '0101...' string to NumPy array of bits."""
    return np.array([int(ch) for ch in s], dtype=np.int32)

def crc14_wsjt(bits77: int) -> int:
    # Generator polynomial (0x2757), width 14, init=0, refin=false, refout=false
    poly = 0x2757
    width = 14
    mask = (1 << width) - 1
    # Pad to 96 bits (77 + 14 + 5)
    nbits = 96
    reg = 0
    for i in range(nbits):
        # bits77 is expected MSB-first (bit 76 first)
        inbit = ((bits77 >> (76 - i)) & 1) if i < 77 else 0
        bit14 = (reg >> (width - 1)) & 1
        reg = ((reg << 1) & mask) | inbit
        if bit14:
            reg ^= poly
    print(bits_to_str(int_to_bits(bits77,77)))
    print(bits_to_str(int_to_bits(reg,14)))
    return reg
        
def check_crc(bits91):
    """Return True if the 91-bit message (77 data + 14 CRC) passes WSJT-X CRC-14."""
    msg_bits = bits91[0:77][::-1]
    crc_bits = bits91[77:91][::-1]  
    new_crc = int_to_bits(crc14_wsjt(bits_to_int(msg_bits)),14)
 #   print(bits_to_str(msg_bits))
 #   print(bits_to_str(crc_bits))
 #   print(bits_to_str(new_crc))
    return np.array_equal(new_crc, crc_bits)


def append_crc(bits77_int):
    """Append 14-bit WSJT-X CRC to a 77-bit message, returning a 91-bit list."""
    bits14_int = crc14_wsjt(bits77_int)
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

