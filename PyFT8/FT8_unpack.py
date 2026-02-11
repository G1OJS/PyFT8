
from string import ascii_uppercase as LTRS, digits as DIGS
CALL_FIELDS = [ (' ' + DIGS + LTRS, 36*10*27**3),   (DIGS + LTRS, 10*27**3), (DIGS + ' ' * 17, 27**3),
                (' ' + LTRS, 27**2),           (' ' + LTRS,   27), (' ' + LTRS,   1) ]
CALL_TOKENS = ("DE", "QRZ", "CQ")
NCALL_TOKENS_PLUS_MAX22 = 2_063_592 + 4_194_304
GRID_RR73s = ('', '', 'RRR', 'RR73', '73')
FT8_MSG_FORMAT = (("i3", 3), ("grid", 16), ("callB",29), ("callA",29))

def get_fields(bits, fmt):
    out = {}
    for name, n in fmt:
        mask = (1 << n) - 1
        out[name] = bits & mask
        bits >>= n
    return out

def unpack(bits77):
    fields = get_fields(bits77, FT8_MSG_FORMAT)
    return (decode_call(fields["callA"]), decode_call(fields["callB"]), decode_grid(fields["grid"]))

def decode_call(call_int):
    call_int >>= 1
    if call_int < 3:
        return CALL_TOKENS[call_int]
    call_int -= NCALL_TOKENS_PLUS_MAX22
    if call_int == 0:
        return '<...>'
    chars = []
    for alphabet, div in CALL_FIELDS:
        idx, call_int = divmod(call_int, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    portable = call_int & 1
    return call + '/P' if portable else call

def decode_grid(grid_int):
    g15 = grid_int & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        return chr(65+a) + chr(65+b) + str(c) + str(d)
    r = g15 - 32400
    if r <= 4:
        return GRID_RR73s[r]
    snr = r - 35
    ir = grid_int >> 15
    prefix = 'R' if ir else ''
    return prefix + f"{snr:+03d}"

