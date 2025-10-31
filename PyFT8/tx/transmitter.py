import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.tx import FT8_encoder
import PyFT8.audio as audio
import PyFT8.timers as timers
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.comms_hub import config, events

global transmitter_state, rig
transmitter_state = {'active':False, 'odd_even':'odd', 'message':'', 'txFreq':1000,
                     'device_str_contains':device_str_contains}
events.subscribe("cycle_start", transmit_message)

rig = IcomCIV()


def set_transmitter_state(new_transmitter_state):
    transmitter_state.update(new_transmitter_state)

def transmit_message(odd_even):
    if(not transmitter_state['active']):
        return
    if(odd_even != transmitter_state['odd_even']):
        return
    msg = transmitter_state['message']
    timers.timedLog(f"Send messasge: {msg['c1']} {msg['c2']} {msg['gr']}", logfile = "QSO.log")
    symbols = FT8_encoder.pack_message(msg['c1'], msg['c2'], msg['gr'])
    audio.create_ft8_wave(symbols, f_base = transmitter_state['txFreq'])
    rig.setPTTON()
    audio.play_wav_to_soundcard(transmitter_state['device_str_contains'])
    rig.setPTTOFF()
