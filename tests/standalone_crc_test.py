bits77 = 0b11100001111111000101001101010111000100000011110100001111000111001010001010001
crc_expected = 0b00111100110010

poly = 0x2757
crc_width = 14

msg = bits77 << 19

reg = 0
regtop = 1 << 14
regmask = regtop -1
for i in range(96):
    outbit = reg & regtop
    reg = (((reg << 1) | (msg & 1)) & regmask)
    if outbit:
        reg ^= poly
    msg = msg >> 1
crc = reg

print(f"{crc_expected:015b}")
print(f"{crc:015b}")





"""
http://www.g4jnt.com/WSJT-X_LdpcModesCodingProcess.pdf

FT8 and FT4 CRC – is 14 bit with the generator polynomial 0x6757 or ‘110011101010111’ (again, the
left-most bit is always ‘1’ and not used). 14 ‘0’s are appended to the 77 bit source data, in the same
was as described above, but there is another quirk in this (and for MSK144) CRC generation. Further ‘0’s
are now added so the resulting source plus extra ‘0’s is padded out to have a length that is a multiple of
8 bits. For the 77+14 bits here, that requires ‘00000’ to be appended making a 96 bit pattern. The 96
bits are left-shifted into the 14 bit shift register, and if the bit just popped out at each shift is a ‘1’, the
contents are XORed with the polynomial.
The 14 bits left in the shift register after the final shift-left form the CRC which is appended to the
original source data to give a data set 91 bits in length 

"""
