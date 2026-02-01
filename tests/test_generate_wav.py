import numpy as np
import time
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager


from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
import PyFT8.audio as audio

WAV = "data/Local_gen_test.wav"

c28a, p1a = pack_ft8_c28("VK1ABC")
c28b, p1b = pack_ft8_c28("VK3JPK")
g15, ir = pack_ft8_g15("QF22")
i3 = 1
n3 = 0

print(f"Expected:  VK1ABC 1110000111111100010100110101")
print(f"Generated: VK1ABC {c28a}")
print(f"Expected:  VK3JPK 1110001000000111101000011110")
print(f"Generated: VK3JPK {c28b}")
print(f"Expected:  QF22 111001010001010")
print(f"Generated: QF22 {g15:015b}")

bits77 = (c28a<<28+1+2+15+3) | (c28b<<2+15+3)|(0<<15+3)|(g15<< 3)|(i3)
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
print(bits91_int)
print("LDPC Parity Bits expected / produced:")
print("01101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits83_int:083b}")
print("Bits174:")
print("111000011111110001010011010101110001000000111101000011110001110010100010100010011110011001001101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits174_int:0174b}")

print(f"Payload symbols  expected:   {'3140652702741323641007602414353532423140652116374640277356422543000253013140652'}")
print(f"Channel symbols modulated:   {''.join([str(s) for s in symbols])}")

# full 15 sec cycle allows for 15/0.16 = 93.75 symbols so need to pad with 14
symbols_framed = [-10]*7
symbols_framed.extend(symbols)  #79 symbols
symbols_framed.extend([-10]*8)
print(f"({len(symbols)} symbols)")
audio_out = audio.AudioOut()
audio_data = audio_out.create_ft8_wave(symbols_framed, f_base = 2500, amplitude = 0.1)
audio_out.write_to_wave_file(audio_data, WAV)



