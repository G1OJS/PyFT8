# NOTE This code is under development. Rx works and UI is OK, but
# QSO functions are under construction
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")


import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import webbrowser
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.rx.FT8_demodulator import cyclic_demodulator
from PyFT8.comms_hub import config, events, TOPICS, start_websockets_server

myCall = 'G1OJS'
myGrid = 'IO90'

testing_from_wsjtx = False
if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    audio.find_audio_devices()

rig = IcomCIV()

def transmit_message(message):
    msg = transmitter_state['message']
    timers.timedLog(f"Send messasge: {msg}", logfile = "QSO.log")
    c1, c2, grid_rpt = msg.split()
    symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
    audio_data = audio.create_ft8_wave(symbols, f_base = config['txfreq'])
    audio.write_wav_file('out.wav', audio_data)
    rig.setPTTON()
    audio.play_wav_to_soundcard()
    rig.setPTTOFF()
    
def initiate_qso(qso_params):
    set_transmitter_state({})
    odd_even = timers.odd_even_now()
    their_call = qso_params['their_call']
    their_tx_freq = qso_params['their_tx_freq']

def process_rx_messages(rxMessage):
    if(not rxMessage):
        return
    their_call = rxMessage['call_b']
    if(not their_call == transmitter_state['their_call']):
        return 
    grid_rpt = rxMessage['grid_rpt']
    timers.timedLog(f"Received reply from {their_call}: {grid_rpt}")
    if(grid_rpt[-2]=="+" or grid_rpt[-2]=="-"):
        set_transmitter_state({'message': f"{callsign} {myCall} R{their_snr:+03d}"})
    if('73' in grid_rpt):
        set_transmitter_state({'message': f"{callsign} {myCall} RR73"})
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

events.subscribe(TOPICS.decoder.decode_dict_rxfreq, process_rx_messages)
events.subscribe(TOPICS.ui.reply_to_cq, initiate_qso)
#events.subscribe(TOPICS.ui.send_cq, )

threading.Thread(target=cyclic_demodulator).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")


timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
