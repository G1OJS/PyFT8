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


# --------------------------
# CRC-14
# --------------------------


def crc14_bits(msg_bits):
    """
    Compute FT8 CRC-14 over bit array (LSB-first order)
    """
    reg = 0
    poly = kCRC_POLY
    for b in msg_bits + [0]*19:
        bit = (b ^ ((reg >> 13) & 1))
        reg = ((reg << 1) & 0x3FFF)
        if bit:
            reg ^= poly
    # Return 14 CRC bits, LSB-first as in FT8 protocol
   # return int_to_bits(0b00111100110010,14)
    return int_to_bits(reg, 14)

def check_crc(bits174):
    if len(bits174) < 91:
        return False
    msg_bits = bits174[:77]
    crc_bits = bits174[77:92]
    new_crc = crc14_bits(msg_bits)
    return np.array_equal(new_crc, crc_bits)

def append_crc(msg_bits):
    """Append 14-bit CRC to a 77-bit message, returning a 91-bit array."""
    crc_bits = crc14_bits(msg_bits)
    return np.concatenate([msg_bits, crc_bits]), crc_bits
