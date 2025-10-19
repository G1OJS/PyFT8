import numpy as np
import re

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

def encode(self):
    costas = [3, 1, 4, 0, 6, 5, 2] # link to FT8 signal class when updated
    """ sourced from https://github.com/vk3jpk/ft8-notes/blob/master/ft8.py """
    msg_crc = self.pack77 << 14 | Message._crc(self.pack77, 0)
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
