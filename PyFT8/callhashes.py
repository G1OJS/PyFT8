call_hashes = {}

def add_call_hashes(call):
    global call_hashes
    chars = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"
    call_padded = (call + "          ")[:11]
    hashes = []
    for m in [10,12,22]:
        x = 0
        for c in call_padded:
            x = 38*x + chars.find(c)
            x = x & ((int(1) << 64) - 1)
        x = x & ((1 << 64) - 1)
        x = x * 47055833459
        x = x & ((1 << 64) - 1)
        x = x >> (64 - m)
        hashes.append(x)
        call_hashes[(x, m)] = call
    return hashes
