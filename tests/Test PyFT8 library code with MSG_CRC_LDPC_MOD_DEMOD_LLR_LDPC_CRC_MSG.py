import numpy as np
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.waterfall import Waterfall
from PyFT8.tx.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config
from PyFT8.signaldefs import FT8

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

symbols_framed = [-10]*7
symbols_framed.extend(symbols)
symbols_framed.extend([-10]*7)
print(f"({len(symbols)} symbols)")
audio_data = audio.create_ft8_wave(symbols_framed, f_base = config.txfreq, amplitude = 0.5)
audio_data = audio_data * np.random.rand(len(audio_data))

decoded_candidates = []
def onDecode(candidate):
    decoded_candidates.append(candidate)

cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, verbose = True, audio_in = audio_data, 
                          max_iters = 60, max_stall = 8, max_ncheck = 33,
                          sync_score_thresh = 4, llr_sd_thresh = 3)

while len(decoded_candidates)<1:
    timers.sleep(0.25)
cycle_manager.running = False

for c in decoded_candidates:
    print(f"{c.message} {c.sync_result['sync_score']:5.2f}, {c.demap_result['snr']:5.0f}, {c.sync_result['origin']}, {c.ldpc_result['n_its']:5.0f}")     
wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates, phase = False, llr_overlay=False)
wf.show_zoom(candidates=decoded_candidates, phase = True, llr_overlay=False)

#print(f"Payload symbols demodulated: {''.join([str(int(s)) for s in candidates[0].payload_symbols])}")
print("bits expected / bits decoded")
print("11100001111111000101001101010111000100000011110100001111000111001010001010001")
if(decoded_candidates):
    for c in decoded_candidates:
        print(''.join(str(int(b)) for b in c.ldpc_result['payload_bits'][:77]))


