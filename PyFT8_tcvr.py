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
from PyFT8.comms_hub import config, events, TOPICS, start_websockets_server, send_to_ui_ws

myCall = 'G1OJS'
myGrid = 'IO90'
global QSO_call, current_tx_message, repeat_counter, last_tx

QSO_call = ''
current_tx_message = None
repeat_counter = 0
last_tx = 0

rig = IcomCIV()

testing_from_wsjtx = False

def transmit_message(msg):
    global QSO_call, current_tx_message, repeat_counter,  last_tx
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

    t_elapsed, t_remaining = timers.time_in_cycle()
    if(t_remaining < 3):
        timers.timedLog("QSO transmit waiting for cycle start", logfile = "QSO.log")
        timers.sleep(t_remaining)

    timers.timedLog(f"PTT ON", logfile = "QSO.log")
    rig.setPTTON()
    audio.play_wav_to_soundcard()
    rig.setPTTOFF()
    last_tx = timers.tnow()
    timers.timedLog(f"PTT OFF", logfile = "QSO.log")

def set_rxFreq(rxfreq):
    send_to_ui_ws("transceiver.set_rxfreq", decode_dict['freq'])
    config.set_rxFreq(decode_dict['freq'])
    
def process_clicked_message(selected_message):
    set_rxFreq(selected_message['freq'])
    reply_to_message(selected_message)

def process_rxfreq_decode(decode):
    # should arrive here earlier than in process_decode
    decode['decode_dict'].update({'priority':True})
    process_decode(decode)

def process_decode(decode):
    decode_dict = decode['decode_dict']
    if(decode_dict['call_b'] == myCall):
        decode_dict.update({'priority':True})        
    send_to_ui_ws("transceiver.decode_dict", decode_dict)
    if (decode_dict['call_b'] == myCall and decode_dict['call_b'] == QSO_call):
        reply_to_messasge(decode_dict)
        
def reply_to_message(decode_dict):
    call_a, call_b, grid_rpt, their_snr = decode_dict['call_a'], decode_dict['call_b'], decode_dict['grid_rpt'], decode_dict['snr']
    if(call_a == "CQ"):
        QSO_call = call_b
        set_rxFreq(decode_dict['freq'])
        current_tx_message = f"{call_b} {myCall} {myGrid}"
        transmit_message(current_tx_message)
    if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
        timers.timedLog(f"QSO reply received: {decode_dict['message']}", logfile = "QSO.log")
        QSO_call = call_b
        set_rxFreq(decode_dict['freq'])
        current_tx_message = f"{call_b} {myCall} R{their_snr:+03d}"
        transmit_message(current_tx_message)
    if('73' in grid_rpt or 'RRR' in grid_rpt):
        timers.timedLog(f"QSO reply received: {decode_dict['message']}", logfile = "QSO.log")
        transmit_message(f"{call_b} {myCall} 73")
        current_tx_message = None
        QSO_call = ''
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

def clear_left_pane(params):
    send_to_ui_ws("transceiver.clear_left", {})

events.subscribe(TOPICS.decoder.decoding_started, clear_left_pane)
events.subscribe(TOPICS.ui.process_clicked_message, process_clicked_message)

if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    config.data.update({"output_device":["CABLE", "Input"]})
    audio.find_audio_devices()

threading.Thread(target=cyclic_demodulator, kwargs=({'onDecode':process_decode, 'onRxFreqDecode':process_rxfreq_decode})).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")


timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
