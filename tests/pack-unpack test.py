import numpy as np
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import Signal, FT8Demodulator
from PyFT8.rx.waterfall import Waterfall
from PyFT8.rx.FT8_decoder import unpack_ft8_c28, unpack_ft8_g15
from PyFT8.tx.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77

calltests = ['WM3PEN', ' G1OJS']
for c in calltests:
    c28 = pack_ft8_c28(c)
    print(unpack_ft8_c28(c28))

gridtests = ['RR73', '-9', 'R-9', 'IO90', 'RRR']
for g in gridtests:
    g15 = pack_ft8_g15(g)
    print(unpack_ft8_g15(g15))

#77 bits and back

def read_wav(filename, chunk_size=1024, sample_rate = 12000):
     import wave
     import numpy as np
     with wave.open(filename, 'rb') as wav:
          assert wav.getframerate() == sample_rate
          assert wav.getnchannels() == 1
          assert wav.getsampwidth() == 2
          audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
     return audio
          
audio = read_wav('210703_133430.wav')
#audio = read_wav('G1OJS_583Hz.wav')

demod = FT8Demodulator(hops_persymb = 1, fbins_pertone = 1)
demod.load(audio)
wf = Waterfall(demod.specbuff, demod.hops_persymb, demod.fbins_pertone, demod.costas, f0=0)
signal = Signal(num_symbols =79, tones_persymb = 8, symbols_persec = 6.25)
tbin_idx = 4*demod.hops_persymb # 4 = random time offset
fbin_idx = 480


#VK1ABC 0b1110000111111100010100110101
#VK3JPK 0b1110001000000111101000011110
#QF22 0b111001010001010
#StandardMessage(VK1ABC VK3JPK QF22) 0b11100001111111000101001101010111000100000011110100001111000111001010001010001

c28a = pack_ft8_c28("VK1ABC")
c28b = pack_ft8_c28("VK3JPK")
g15 = pack_ft8_g15("QF22")
i3 = 1
n3 = 0

print(f"Expected:  VK1ABC 1110000111111100010100110101")
print(f"Generated: VK1ABC {c28a:028b}")
print(f"Expected:  VK3JPK 1110001000000111101000011110")
print(f"Generated: VK3JPK {c28b:028b}")
print(f"Expected:  QF22 111001010001010")
print(f"Generated: QF22 {g15:015b}")


bits77 = (c28a<<28+1+2+15+3) | (c28b<<2+15+3)|(0<<15+3)|(g15<< 3)|(i3)
bits77 = 0b11100001111111000101001101010111000100000011110100001111000111001010001010001
print("bits expected / bits encoded")
print("11100001111111000101001101010111000100000011110100001111000111001010001010001")
print(f"{bits77:077b}")


symbols, bits174_int, bits91_int, bits14_int, bits83_int = encode_bits77(bits77)
print("CRC expected / produced:")
print("00111100110010")
print(f"{bits14_int:014b}")
print("Bits91:")
print("1110000111111100010100110101011100010000001111010000111100011100101000101000100111100110010")
print(f"{bits91_int:091b}")
print("LDPC Parity Bits expected / produced:")
print("01101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits83_int:083b}")
print("Bits174:")
print("111000011111110001010011010101110001000000111101000011110001110010100010100010011110011001001101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits174_int:0174b}")

print(f"Payload symbols  expexted: {'7027413236410076024143535324211637464027735642254300025301'}")
print(f"Payload symbols modulated: {''.join([str(symbols[idx]) for idx in signal.payload_symbol_idxs])}")
for t_idx, symbol in enumerate(symbols):
    for tbin in range(demod.hops_persymb):
        for fbin in range(demod.fbins_pertone):
            t = tbin_idx + t_idx * demod.hops_persymb + tbin
            f = fbin_idx + symbol * demod.fbins_pertone + (fbin - demod.fbins_pertone//2)
            demod.specbuff.complex[t, f] = 500000


candidates = demod.get_candidates(topN=1, f0=0)
output = demod.demodulate(candidates, "000000")
wf.update(candidates = candidates, show_n_candidates = 3)
print(f"Payload symbols demodulated: {''.join([str(int(s)) for s in candidates[0].payload_symbols])}")

print("bits expected / bits decoded")
print("11100001111111000101001101010111000100000011110100001111000111001010001010001")
print([int(b) for b in candidates[0].payload_bits])

for l in output:
     print(l)
