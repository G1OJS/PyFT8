import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
import numpy as np

# put this in signaldefs.py and include as part of the FTx spec

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


def append_crc(bits77_int):
    """Append 14-bit WSJT-X CRC to a 77-bit message, returning a 91-bit list."""
    bits14_int = crc14(bits77_int)
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

def check_crc(bits91_int):
    """Return True if the 91-bit message (77 data + 14 CRC) passes WSJT-X CRC-14."""
    bits14_int = bits91_int & 0b11111111111111
    bits77_int = bits91_int >> 14
    return bits14_int == crc14(bits77_int)

def int_to_bitsLE(n, width):
    """Return [b(width-1), ..., b0], MSB-first."""
    return [ (n >> (width - 1 - i)) & 1 for i in range(width) ]

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

def verify_crc_code():
    bits77_int = 0b11100001111111000101001101010111000100000011110100001111000111001010001010001
    print(f"CRC loop test: check_crc(append_crc(bits77_int)) = { check_crc(append_crc(bits77_int))}")
