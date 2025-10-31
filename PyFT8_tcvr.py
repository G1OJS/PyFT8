import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import sys
import webbrowser

# NOTE This code is under development. Rx works and UI is OK, but
# QSO functions are under construction

sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
from PyFT8.rx.FT8_demodulator import cyclic_demodulator
from PyFT8.comms_hub import config, events, start_websockets_server
from PyFT8.rig.IcomCIV import IcomCIV
import PyFT8.timers as timers
import json
icom = IcomCIV()
myCall = 'G1OJS'
myGrid = 'IO90'

PyFT8_logfile = "pyft8.txt"
wsjtx_logfile = "wsjtx.txt"

class ClickHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        super().do_GET()

def get_reply(from_call, wait_cycles = 0):
    if(wait_cycles >= 0):
        _ , t_remain = timers.time_in_cycle()
        t_remain += wait_cycles*15
        time.sleep(t_remain+1) # needs to wait for a message 'rx frequency decoded'
    with open("rxFreq_data.json", "r") as f:
        for s in reversed(f.readlines()):
            decode = next((item for item in reversed(eval(s)) if item["call_b"] == from_call), None)
            if(decode): return decode['grid_rpt']  

def initiate_qso(callsign, wait_for_next = False):
    _ , t_remain = timers.time_in_cycle()
    clear_rxWindow()
    timers.timedLog(f"Initiate QSO with {callsign}")
    if(t_remain < 12.8):
        timers.timedLog(f"QSO: Not enough time: t_remain = {t_remain} seconds")
        time.sleep(t_remain+15)
    wait_cycles = -1
    while True:
        timers.timedLog(f"Send messasge: {callsign} {myCall} {myGrid}", logfile = "QSO.log")
        send_message(icom,callsign, myCall, myGrid, int(config['txFreq']), wait_cycles = wait_cycles)
        wait_cycles = 1
        their_reply = get_reply(callsign, wait_cycles = wait_cycles)
        timers.timedLog(f"Received reply: {their_reply}", logfile = "QSO.log")
        if(not their_reply): continue
        if(their_reply[-3] == "+" or their_reply[-3] == "-"): break        
    wait_cycles = -1
    while True:
        their_snr = int(their_reply[-3:])
        timers.timedLog(f"Send messasge: {callsign} {myCall} R{their_snr:+03d}", logfile = "QSO.log")
        send_message(icom,callsign, myCall, f"R{their_snr:+03d}", int(config['txFreq']), wait_cycles = wait_cycles)
        their_reply = get_reply(callsign, wait_cycles = wait_cycles)
        timers.timedLog(f"Received reply: {their_reply}", logfile = "QSO.log")
        if('73' in their_reply): break
    timers.timedLog(f"Send messasge reply: {callsign} {myCall} 73", logfile = "QSO.log")
    send_message(icom,callsign, myCall, '73', int(config['txFreq']), wait_cycles = wait_cycles)
    
def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), ClickHandler)
    server.serve_forever()

#threading.Thread(target=cyclic_demodulator, args=(["CABLE","Output"],)).start()
threading.Thread(target=cyclic_demodulator, args=(["Mic","CODEC"],)).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")

timers.timedLog(f"Starting websockets server")
import asyncio
asyncio.run(start_websockets_server())

#send_message(icom,"CQ","G1OJS","IO90", 1000)

#send_message(icom,"X1XXX","G1OJS","+03", 1000)
#send_message(icom,"X1XXX","G1OJS","-08", 1000)

#send_message(icom,"X1XXX","G1OJS","R+08", 1000)
#send_message(icom,"X1XXX","G1OJS","R-08", 1000)

#send_message(icom,"X1XXX","G1OJS","RRR", 1000)

#send_message(icom,"X1XXX","G1OJS","RR73", 1000)

#send_message(icom,"X1XXX","G1OJS","73", 1000)
#send_message(icom,"X1XXX","G1O","73", 1000)
    
