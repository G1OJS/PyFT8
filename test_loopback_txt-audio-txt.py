import numpy as np
from PyFT8.waterfall import Waterfall
import PyFT8.timers as timers
from PyFT8.sigspecs import FT8
from PyFT8.cycle_manager import Cycle_manager

from PyFT8.FT8_encoder import pack_ft8_c28, pack_ft8_g15, encode_bits77
import PyFT8.audio as audio

wav_file = "Local_gen_test.wav"

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
audio_out = audio.AudioOut()
audio_data = audio_out.create_ft8_wave(symbols_framed, f_base = 3000, amplitude = 0.1, added_noise = -20)
audio_out.write_to_wave_file(audio_data, wav_file)

global decoded_candidates
decoded_candidates = []
first = True
def onDecode(c):
    global first
    global cycle_manager
    if(first):
        first = False
        heads = ['Cycle', 'End_cyc+', 'Rx call', 'Tx call', 'GrRp', 'SyncScr', 'snr', 't0_idx', 'f0_idx', 'ncheck']
        print(''.join([f"{t:>8} " for t in heads]))
    dd = c.decode_dict
    t_decode = (timers.tnow()+7) % 15 -7
    vals = [f"{dd['cyclestart_str']} {t_decode:8.2f}", dd['call_a'], dd['call_b'], dd['grid_rpt'],
            f"{dd['sync_score']:>5.2f}",  f"{dd['snr']:5.0f}", dd['t0_idx'], dd['f0_idx'], dd['ncheck_initial']]
    print(''.join([f"{t:>8} " for t in vals]))
    decoded_candidates.append(c)

print("Bits91:")
print("1110000111111100010100110101011100010000001111010000111100011100101000101000100111100110010")
cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, audio_in_wav = wav_file, 
                          max_iters = 10,  max_ncheck = 28, 
                          sync_score_thresh = 8, max_cycles = 2, return_candidate = True)

while cycle_manager.running:
    timers.sleep(0.1)

unique_decoded_candidates = list(set(decoded_candidates))
print(f"DONE. {len(unique_decoded_candidates)} unique decodes.")    

print("bits expected / bits decoded")
print("11100001111111000101001101010111000100000011110100001111000111001010001010001")
if(decoded_candidates):
    for c in decoded_candidates:
        print(''.join(str(int(b)) for b in c.payload_bits[:77]))

wf = Waterfall(cycle_manager.spectrum)
wf.update_main(candidates=decoded_candidates)
wf.show_zoom(candidates=decoded_candidates)
