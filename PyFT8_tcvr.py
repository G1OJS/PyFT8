import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import time
import webbrowser
import subprocess
from PyFT8.rx import liveRx
from PyFT8.tx import FT8_encoder
from PyFT8.rig.IcomCIV import IcomCIV
import PyFT8.tx.audio_out as audio_out
import json
icom = IcomCIV()
cycle_length = 15
myCall = 'G1OJS'
myGrid = 'IO90'

def time_in_cycle():
    t_elapsed = (time.time() % cycle_length)
    t_remaining = cycle_length - t_elapsed 
    return t_elapsed, t_remaining

class ClickHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/select_"):
            callsign =  self.path.strip("/").replace("select_", "").replace(".txt", "")
            threading.Thread(target=initial_reply, args=(callsign,)).start()
        super().do_GET()

def initial_reply(callsign):
    print(callsign, type(callsign))
    print(f"Initial reply to {callsign}\n")
    send_message(callsign, myCall, myGrid, 1000)

def send_message(c1,c2,gr, freq):
    symbols = FT8_encoder.pack_message(c1,c2,gr, freq)
    audio_out.create_ft8_wave(symbols)
    _ , t_remain = time_in_cycle()
    time.sleep(t_remain)
    icom.setPTTON()
    audio_out.play_ft8_wave()
    icom.setPTTOFF()

def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), ClickHandler)
    server.serve_forever()

threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")
threading.Thread(target=liveRx.run).start()


    





