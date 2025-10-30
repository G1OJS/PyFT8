import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.tx import FT8_encoder
import PyFT8.audio as audio

def send_message(rig,c1,c2,gr, freq, wait_cycles = 0):
    symbols = FT8_encoder.pack_message(c1,c2,gr)
    audio.create_ft8_wave(symbols, f_base = freq)
    if(wait_cycles >= 0):
        _ , t_remain = timers.time_in_cycle()
        t_remain += wait_cycles*15
        time.sleep(t_remain)
    rig.setPTTON()
    audio.play_ft8_wave()
    rig.setPTTOFF()
