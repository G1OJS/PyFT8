hashed_calls = []

def FT8_unpack(bits):
    # need to add PW8BR RR73; HK1J  messages i3=0 n3 =1
    # need to add callsign hashing
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    ir = int(bits[58])
    call_a = unpack_ft8_c28(int(''.join(str(b) for b in bits[0:28]), 2), bits[28])
    call_b = unpack_ft8_c28(int(''.join(str(b) for b in bits[29:57]), 2), bits[57])
    grid_rpt = unpack_ft8_g15(int(''.join(str(b) for b in bits[59:74]), 2), ir)
    return (call_a, call_b, grid_rpt)


def unpack_ft8_c28(c28, p1):
    from string import ascii_uppercase as ltrs, digits as digs
    if c28<3:
        return ["DE", 'QRZ','CQ'][c28]
    n = c28 - 2_063_592 - 4_194_304 # NTOKENS, MAX22
    if n == 0:
        return '<...>'
    charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
    divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
    indices = []
    for d in divisors:
        i, n = divmod(n, d)
        indices.append(i)
    callsign = ''.join(t[i] for t, i in zip(charmap, indices)).strip()
    if(p1):
        callsign = callsign + "/P"
    save_hash(callsign)
    return callsign

def save_hash(call):
    full_charset = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/'
    i = 0
    for c in call.ljust(11):
        i = i * len(full_charset) + full_charset.index(c)       
    hash64 = (i * 47055833459) & (2**64 - 1)
    hash22 = hash64 >> 42
    hash12 = hash64 >> 52
    hash10 = hash64 >> 54
    hashed_calls.append( (hash10, hash12, hash22) )

def unpack_ft8_g15(g15, ir):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    R = '' if (ir == 0) else 'R'
    return f"{R}{snr:+03d}"


