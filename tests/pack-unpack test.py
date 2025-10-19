import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_decoder import unpack_ft8_c28, unpack_ft8_g15
from PyFT8.tx.FT8_encoder import pack_ft8_c28, pack_ft8_g15

calltests = ['WM3PEN', ' G1OJS']
for c in calltests:
    c28 = pack_ft8_c28(c)
    print(unpack_ft8_c28(c28))

gridtests = ['RR73', '-9', 'R-9', 'IO90', 'RRR']
for g in gridtests:
    g15 = pack_ft8_g15(g)
    print(unpack_ft8_g15(g15))

