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
from PyFT8.tx.transmitter import set_transmitter_state, transmitter_state

myCall = 'G1OJS'
myGrid = 'IO90'

#input_device = ["Microphone","CODEC"]
output_device =["Speaker", "CODEC"]
input_device = ["CABLE", "Output"]


set_transmitter_state({'device_str_contains':output_device})
    
def initiate_qso(ui_command):
   # clear_rxWindow()
    set_transmitter_state({})
    odd_even = timers.odd_even_now()
    their_call = ui_command['call']
    set_transmitter_state({'their_call':their_call , 'active':True,
                           'odd_even':odd_even, 'message': f"{their_call} {myCall} {myGrid}"})
    events.publish("cycle_start", odd_even) # start this cycle now

def process_rx_messages(rxMessage):
    their_call = rxMessage['call_b']
    if(not their_call == transmitter_state['their_call']): return 
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

events.subscribe("rxFreqMessage", process_rx_messages)
events.subscribe("Reply_to", initiate_qso)

threading.Thread(target=cyclic_demodulator, args=(input_device,)).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")


timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())


    
