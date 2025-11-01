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
global QSO_their_call, current_tx_message, repeat_counter
QSO_their_call = ''
current_tx_message = None
repeat_counter = 0

rig = IcomCIV()

testing_from_wsjtx = False

def transmit_message(msg):
    global QSO_their_call, current_tx_message, repeat_counter
    if(not msg): return
    repeat_counter = repeat_counter + 1 if( msg == current_tx_message ) else 0
    if(repeat_counter >= 3):
        return
    timers.timedLog(f"Send messasge: ({repeat_counter}) {msg}", logfile = "QSO.log")
    c1, c2, grid_rpt = msg.split()
    symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
    audio_data = audio.create_ft8_wave(symbols, f_base = config.data['txfreq'])
    audio.write_wav_file('out.wav', audio_data)
    rig.setPTTON()
    audio.play_wav_to_soundcard()
    rig.setPTTOFF()
    
def initiate_qso(qso_params):
    global QSO_their_call, current_tx_message, repeat_counter
    odd_even = timers.odd_even_now()
    QSO_their_call = qso_params['their_call']
    # no waiting here, just transmit now
    current_tx_message = f"{QSO_their_call} {myCall} {myGrid}"
    transmit_message(current_tx_message)

def wait_for_Tx_cycle():
    # if machine transmit is ready before end of Rx cycle, wait for beginning of Tx cycle
    t_elapsed, t_remaining = timers.time_in_cycle() 
    if(t_elapsed > 2): timers.sleep(t_remaining) 

def process_rx_messages(decode_dict):
    global QSO_their_call, current_tx_message, repeat_counter
    their_call = None
    if(decode_dict):
        their_call = decode_dict['call_b']  
    if(not their_call == QSO_their_call):
        wait_for_Tx_cycle()
        transmit_message(current_tx_message)
    if(not decode_dict):
        return
    grid_rpt = decode_dict['grid_rpt']
    timers.timedLog(f"Received reply from {their_call}: {grid_rpt}", logfile = "QSO.log")
    if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
        their_snr = decode_dict['snr']
        current_tx_message = f"{QSO_their_call} {myCall} R{their_snr:+03d}"
        wait_for_Tx_cycle()
        transmit_message(current_tx_message)
    if('73' in grid_rpt):
        wait_for_Tx_cycle()
        transmit_message(f"{QSO_their_call} {myCall} 73")
        current_tx_message = None
    

    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

events.subscribe(TOPICS.decoder.decode_dict_rxfreq, process_rx_messages)
events.subscribe(TOPICS.ui.reply_to_cq, initiate_qso)
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


    
