import numpy as np
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import FT8Demodulator, unpack_ft8_c28, unpack_ft8_g15
from PyFT8.rx.waterfall import Waterfall
from PyFT8.tx.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config

demod = FT8Demodulator()
#config.decoder_search_limit = 500

#VK1ABC 0b1110000111111100010100110101
#VK3JPK 0b1110001000000111101000011110
#QF22 0b111001010001010
#StandardMessage(VK1ABC VK3JPK QF22) 0b11100001111111000101001101010111000100000011110100001111000111001010001010001

c28a = pack_ft8_c28("VK1ABC")
c28b = pack_ft8_c28("VK3JPK")
g15, ir = pack_ft8_g15("QF22")
i3 = 1
n3 = 0

print(f"Expected:  VK1ABC 1110000111111100010100110101")
print(f"Generated: VK1ABC {c28a:028b}")
print(f"Expected:  VK3JPK 1110001000000111101000011110")
print(f"Generated: VK3JPK {c28b:028b}")
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
print("LDPC Parity Bits expected / produced:")
print("01101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits83_int:083b}")
print("Bits174:")
print("111000011111110001010011010101110001000000111101000011110001110010100010100010011110011001001101010111110101110000011111111010100101110011011100110010000000000011100010000001")
print(f"{bits174_int:0174b}")

print(f"Payload symbols  expected:   {'7027413236410076024143535324211637464027735642254300025301'}")
print(f"Channel symbols modulated:   {''.join([str(s) for s in symbols])}")


# load audio early as we want to overwrite some of it
wav_file='210703_133430.wav'
audio_in = audio.read_wav_file(wav_file)
demod.load_audio(audio_in)
w,h = demod.spectrum.fine_grid_complex.shape

t0_idx = 6
f0_idx = 320
rel_strength = 10
# 'modulate' onto channel grid
demod.spectrum.fill_arrays(np.random.rand(w, h))
m = np.max(np.abs(demod.spectrum.fine_grid_complex))  * rel_strength
for symb_idx, tone_idx in enumerate(symbols):
    f0 = f0_idx + tone_idx * demod.fbins_pertone
    f1 = f0 + demod.fbins_pertone
    t0 = t0_idx + symb_idx * demod.hops_persymb
    t1 = t0 + demod.hops_persymb
    demod.spectrum.fine_grid_complex[t0:t1, f0:f1] = m
demod.spectrum.fill_arrays(demod.spectrum.fine_grid_complex)


# 'demodulate' as with any audio frame
timers.timedLog(f"Start to Load audio from {wav_file}")

candidates = demod.find_candidates()
decoded_candidates = []
for c in candidates:
    decode = demod.demodulate_candidate(c, silent=True)
    if(decode):
        decoded_candidates.append(c)
        d = decode['decode_dict']
        print(d['call_a'], d['call_b'], d['grid_rpt'], c.score )
wf = Waterfall(demod.spectrum, f0=0, f1=3500)

wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates, phase = False, llr_overlay=False)
#wf.show_zoom(candidates=decoded_candidates, phase = True, llr_overlay=False)

#print(f"Payload symbols demodulated: {''.join([str(int(s)) for s in candidates[0].payload_symbols])}")
print("bits expected / bits decoded")
print("11100001111111000101001101010111000100000011110100001111000111001010001010001")
if(decoded_candidates):
    for c in decoded_candidates:
        print(''.join(str(int(b)) for b in c.payload_bits[:77]))


