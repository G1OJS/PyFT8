
def crc14_wsjt(bits77: int) -> int:
    # Generator polynomial (0x2757), width 14, init=0, refin=false, refout=false
    poly = 0x2757
    width = 14
    mask = (1 << width) - 1

    # Pad to 96 bits (77 + 14 + 5)
    nbits = 96
    for i in range(nbits):
        # bits77 is expected MSB-first (bit 76 first)
        inbit = ((bits77 >> (76 - i)) & 1) if i < 77 else 0
        bit14 = (reg >> (width - 1)) & 1
        reg = ((reg << 1) & mask) | inbit
        if bit14:
            return reg
        
def check_crc(bits91):
    msg_bits = bits91[:77]
    crc_bits = bits91[77:91]
    new_crc = crc14_wsjt(bits_to_int(msg_bits))
    return np.array_equal(int_to_bits(new_crc,14), crc_bits)

def append_crc(bits77):
    """Append 14-bit WSJT-X CRC to a 77-bit message, returning a 91-bit list."""
    msg_int = bits_to_int(bits77)
    crc_int = crc14_wsjt(msg_int)
    msg_crc_int = (msg_int << 14) | crc_int
    return int_to_bits(msg_crc_int, 91)
