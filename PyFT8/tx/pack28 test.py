def pack_ft8_c28(call):
    if (call == "CQ"): return 2
    from string import ascii_uppercase as ltrs, digits as digs
    import re
    import numpy as np
    m = int(re.search(r"\d", call).start())
    if(m == 1): call = ' '+call
    lc = len(call)
    m = int(re.search(r"\d", call).start())
    print(m, lc)
    if (m == lc-3):
        call = call + ' '
    charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
    factors = np.array([36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1])
    indices = np.array([cmap.index(call[i]) for i, cmap in enumerate(charmap)])
    return int(np.sum(factors * indices) + 2_063_592 + 4_194_304)

print(pack_ft8_c28('G1OJA'))
