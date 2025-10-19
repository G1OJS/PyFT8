import numpy as np
import re

def pack77(call1, call2, grid):
    n28a = pack_ft8_c28(call1)
    n28b = pack_ft8_c28(call2)
    igrid4 = pack_ft8_g15(grid)
    i3 = 1 
    n28a <<= 1 
    n28b <<= 1
    b77 = bytearray()
    b77[0] = (n28a >> 21) & 0xFF
    b77[1] = (n28a >> 13) & 0xFF
    b77[2] = (n28a >> 5) & 0xFF
    b77[3] = ((n28a << 3) & 0xFF) | ((n28b >> 26) & 0xFF)
    b77[4] = (n28b >> 18) & 0xFF
    b77[5] = (n28b >> 10) & 0xFF
    b77[6] = (n28b >> 2) & 0xFF
    b77[7] = ((n28b << 6) & 0xFF) | ((igrid4 >> 10) & 0xFF)
    b77[8] = (igrid4 >> 2) & 0xFF
    b77[9] = ((igrid4 << 6) & 0xFF) | ((i3 << 3) & 0xFF)
    return b77

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

def crc(msg, chk):
        remainder = (msg << (crc_padded_bits - msg_bits)) | chk
        mask = 1 << (crc_padded_bits - 1)
        shifted_poly = ((1 << crc_bits) | crc_polynomial) << (crc_padded_bits - crc_bits - 1)
        for i in range(crc_padded_bits - crc_bits):
            if (remainder & mask):
                remainder ^= shifted_poly
            mask >>= 1
            shifted_poly >>= 1
        return remainder      

def encode(bits77):
    costas = [3, 1, 4, 0, 6, 5, 2] # link to FT8 signal class when updated
    """ sourced from https://github.com/vk3jpk/ft8-notes/blob/master/ft8.py """
    msg_crc = bits77 << 14 | crc(bits77, 0)
    parity = 0
    for row in generator_matrix:
        parity = parity << 1
        parity = parity | (bin(row & msg_crc).count('1') % 2)
    codeword = (msg_crc << 83) | parity
    msg_symbols = []
    mask = (1 << 3) - 1
    for i in range(174 // 3):
        msg_symbols.insert(0, gray_map[codeword & mask])
        codeword = codeword >> 3
    symbols = costas + msg_symbols[:encoded_symbols // 2] + costas + msg_symbols[encoded_symbols // 2:] + costas   
    return symbols


from typing import List

def parity8(x: int) -> int:
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    return x % 2

def encode174(message: List[int], codeword: List[int], 
              kFTX_LDPC_generator: List[List[int]], 
              FTX_LDPC_N_BYTES: int, FTX_LDPC_K_BYTES: int, 
              FTX_LDPC_K: int, FTX_LDPC_M: int):
    for j in range(FTX_LDPC_N_BYTES):
        codeword[j] = message[j] if j < FTX_LDPC_K_BYTES else 0
    col_mask = (0x80 >> (FTX_LDPC_K % 8))
    col_idx = FTX_LDPC_K_BYTES - 1
    for i in range(FTX_LDPC_M):
        nsum = 0
        for j in range(FTX_LDPC_K_BYTES):
            bits = message[j] & kFTX_LDPC_generator[i][j]
            nsum ^= parity8(bits)
        if nsum % 2:
            codeword[col_idx] |= col_mask
        col_mask >>= 1
        if col_mask == 0:
            col_mask = 0x80
            col_idx += 1
