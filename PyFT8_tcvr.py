# NOTE This code is under development. Rx works and UI is OK, but
# QSO functions are under construction
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")


import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import webbrowser
import PyFT8.timers as timers
from PyFT8.rx.FT8_demodulator import cyclic_demodulator
from PyFT8.comms_hub import config, events, start_websockets_server
from PyFT8.tx.transmitter import set_transmitter_state

myCall = 'G1OJS'
myGrid = 'IO90'

#input_device = ["Mic","CODEC"]
#output_device =["Speaker", "CODEC"]

input_device = ["CABLE","Output"]
output_device =["CABLE", "Input"]
    
def initiate_qso(ui_command):
   # clear_rxWindow()
    callsign = ui_command['call']
    timers.timedLog(f"Initiate QSO with {callsign}")
    odd_even = timers.odd_even_now()
    set_transmitter_state({'active':True,'odd_even':odd_even, 'message': f"{callsign} {myCall} {myGrid}"})
    events.publish("cycle_start",odd_even)

def process_rx_messages(rxMessage):
    timers.timedLog(f"Received reply from {rxMessage['call_b']}: {rxMessage['grid_rpt']}")
    # if report, transmitter.set_transmitter_state({'message':f"{callsign} {myCall} R{their_snr:+03d}" })
    # if 73, transmitter.set_transmitter_state({'message':f"73"})
    pass
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

events.subscribe("rxFreqMessage", process_rx_messages)
events.subscribe("Reply_to", initiate_qso)

threading.Thread(target=cyclic_demodulator, args=(input_device,)).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")

timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
