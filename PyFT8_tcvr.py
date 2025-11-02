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
global QSO_call_b, current_tx_message, repeat_counter, last_tx
QSO_call_b = ''
current_tx_message = None
repeat_counter = 0
last_tx = 0

rig = IcomCIV()

testing_from_wsjtx = False

def transmit_message(msg):
    global QSO_call_b, current_tx_message, repeat_counter,  last_tx
    if(not msg):
        timers.timedLog("QSO transmit skip, no message to transmit", logfile = "QSO.log")
        return
    repeat_counter = repeat_counter + 1 if( msg == current_tx_message ) else 0
    if(repeat_counter >= 3):
        timers.timedLog("QSO transmit skip, repeat count too high", logfile = "QSO.log")
        return
    timers.timedLog(f"Send message: ({repeat_counter}) {msg}", logfile = "QSO.log")
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
    call_a, call_b, grid_rpt, their_snr  = selected_message['call_a'], selected_message['call_b'], selected_message['grid_rpt'], selected_message['snr']
    
    if(call_a == "CQ"):
        current_tx_message = f"{call_b} {myCall} {myGrid}"
        transmit_message(current_tx_message)

    if(call_a == myCall and (grid_rpt[-3]=="+" or grid_rpt[-3]=="-")):
        current_tx_message = f"{call_b} {myCall} R{their_snr:+03d}"
        transmit_message(current_tx_message)

#decode_dict = {'cyclestart_str': '251101_232315', 'freq': '2000', 'call_a': 'G1OJS', 'call_b': 'W1JTX',
#        'grid_rpt': '+36', 't0_idx': 4, 'dt': ' 0.2', 'snr': 24, 'message': 'G1OJS W1JTX +36'}
def process_rx_messages(decode_dict):
    if(timers.tnow() - last_tx < 7):
        timers.timedLog("QSO processing skip, time to close to end of last tx", logfile = "QSO.log")
        return # wrong cycle
    if(not decode_dict):
        timers.timedLog("QSO processing skip, no current Rx freq decode", logfile = "QSO.log")
        return # no decode
    timers.timedLog(f"QSO reply received: {decode_dict['message']}", logfile = "QSO.log")
    call_a, call_b, grid_rpt, their_snr = decode_dict['call_a'], decode_dict['call_b'], decode_dict['grid_rpt'], decode_dict['snr']

    if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
        current_tx_message = f"{call_b} {myCall} R{their_snr:+03d}"
        transmit_message(current_tx_message)

    if('73' in grid_rpt or 'RRR' in grid_rpt):
        transmit_message(f"{call_b} {myCall} 73")
        current_tx_message = None
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

events.subscribe(TOPICS.decoder.decode_dict_rxfreq, process_rx_messages)
events.subscribe(TOPICS.ui.reply_to_message, reply_to_message)
#events.subscribe(TOPICS.ui.send_cq, )


if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    config.data.update({"output_device":["CABLE", "Input"]})
    audio.find_audio_devices()

threading.Thread(target=cyclic_demodulator).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")


timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
