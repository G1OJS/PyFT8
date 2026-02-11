
def check_crc(bits91_int):
    bits77_int = bits91_int >> 14
    if(bits77_int > 0):
        crc14_int = 0
        for i in range(96):
            inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
            bit14 = (crc14_int >> (14 - 1)) & 1
            crc14_int = ((crc14_int << 1) & ((1 << 14) - 1)) | inbit
            if bit14:
                crc14_int ^= 0x2757
        if(crc14_int == bits91_int & 0b11111111111111):
            return bits77_int

def _crc14(bits77_int: int) -> int:
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
    bits14_int = _crc14(bits77_int)
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

