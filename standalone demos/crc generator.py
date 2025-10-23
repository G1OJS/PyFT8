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

bits77 = 0b11100001111111000101001101010111000100000011110100001111000111001010001010001
crc_expected = 0b00111100110010

crc = crc14(bits77)
print(f"Expected : {crc_expected:014b}")
print(f"Calculated: {crc:014b}")
