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
