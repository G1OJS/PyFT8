import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.tx import FT8_encoder
import PyFT8.audio as audio
import PyFT8.timers as timers
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.comms_hub import config, events

global transmitter_state, rig
transmitter_state = {'active':False, 'odd_even':'odd', 'message':'', 'txFreq':1000,
                     'their_call':'', 'device_str_contains':''}

rig = IcomCIV()

def set_transmitter_state(new_transmitter_state):
    timers.timedLog(f"Update transmitter state {new_transmitter_state}")
    transmitter_state.update(new_transmitter_state)

def transmit_message(odd_even):
    timers.timedLog(f"Check if transmit needed for odd_even = {odd_even}")
    if(not transmitter_state['active']):
        return
    if(odd_even != transmitter_state['odd_even']):
        return
    msg = transmitter_state['message']
    timers.timedLog(f"Send messasge: {msg}", logfile = "QSO.log")
    c1, c2, grid_rpt = msg.split()
    symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
    audio_data = audio.create_ft8_wave(symbols, f_base = transmitter_state['txFreq'])
    audio.write_wav_file('out.wav', audio_data)
    rig.setPTTON()
    audio.play_wav_to_soundcard(transmitter_state['device_str_contains'])
    rig.setPTTOFF()
    if('73' in msg):
        set_transmitter_state({'active':False})

events.subscribe("cycle_start", transmit_message)
