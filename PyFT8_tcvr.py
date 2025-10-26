import threading
import time
from PyFT8.rx import liveRx
from PyFT8.tx import FT8_encoder
from PyFT8.rig.IcomCIV import IcomCIV
import PyFT8.tx.audio_out as audio_out

CYCLE = 15

icom = IcomCIV()

#threading.Thread(target=liveRx.run).start()

symbols = FT8_encoder.pack_message("CQ", "G1OJS", "IO90", 1000)
audio_out.create_ft8_wave(symbols)
t = time.time()
t_to_next = CYCLE - (t % CYCLE)
time.sleep(t_to_next)
icom.setPTTON()
audio_out.play_ft8_wave()
icom.setPTTOFF()

