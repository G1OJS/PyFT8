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
import PyFT8.tx.FT8_encoder as FT8_encoder
from PyFT8.comms_hub import config, events, TOPICS, start_websockets_server

myCall = 'G1OJS'
myGrid = 'IO90'
global QSO_their_call, current_tx_message, repeat_counter, last_tx
QSO_their_call = ''
current_tx_message = None
repeat_counter = 0
last_tx = 0

rig = IcomCIV()

testing_from_wsjtx = False

def transmit_message(msg):
    global QSO_their_call, current_tx_message, repeat_counter,  last_tx
    if(not msg): return
    repeat_counter = repeat_counter + 1 if( msg == current_tx_message ) else 0
    if(repeat_counter >= 3):
        return
    timers.timedLog(f"Send messasge: ({repeat_counter}) {msg}", logfile = "QSO.log")
    c1, c2, grid_rpt = msg.split()
    symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
    audio_data = audio.create_ft8_wave(symbols, f_base = config.data['txfreq'])
    audio.write_wav_file('out.wav', audio_data)
    timers.timedLog(f"PTT ON", logfile = "QSO.log")
    rig.setPTTON()
    audio.play_wav_to_soundcard()
    rig.setPTTOFF()
    last_tx = timers.tnow()
    timers.timedLog(f"PTT OFF", logfile = "QSO.log")
    
def reply_to_message(selected_message):
    first_call, their_call, grid_rpt = selected_message['first_call'], selected_message['their_call'], selected_message['grid_rpt']

    if(first_call == "CQ"):
        current_tx_message = f"{their_call} {myCall} {myGrid}"
        transmit_message(current_tx_message)

    if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
        their_snr = decode_dict['snr']
        current_tx_message = f"{their_call} {myCall} R{their_snr:+03d}"
        transmit_message(current_tx_message)

    if('73' in grid_rpt or 'RRR' in grid_rpt):
        transmit_message(f"{their_call} {myCall} 73")
        current_tx_message = None
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

#events.subscribe(TOPICS.decoder.decode_dict_rxfreq, process_rx_messages)
events.subscribe(TOPICS.ui.reply_to_message, reply_to_message)
#events.subscribe(TOPICS.ui.send_cq, )


if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    audio.find_audio_devices()

threading.Thread(target=cyclic_demodulator).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")


timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
