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
import PyFT8.timers as timers
import json
icom = IcomCIV()
cycle_length = 15
myCall = 'G1OJS'
myGrid = 'IO90'

global config
config = {'txFreq':1500, 'rxFreq':1500 }
def dump_config():
    with open("config.json", "w") as f:
        json.dump(config, f)        

class ClickHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/select_"):
            threading.Thread(target=process_click_content, args=(self.path,)).start()  
        super().do_GET()

def process_click_content(clickedpath):
    global config
    text = clickedpath.strip("/").replace("select_", "").replace(".txt", "").replace('%20',' ')
    idx, data = text.split("_")
    idx = int(idx)
    if(idx == 1):
        config['rxFreq'] = int(data)
        print(f"Set Rx freq to {config['rxFreq']}")
        dump_config()

    if(idx == 2): call_next = str(data)
    if(idx == 3): call_now = str(data)
     
def initial_reply(callsign):
    print(callsign, type(callsign))
    print(f"Initial reply to {callsign}\n")
    send_message(callsign, myCall, myGrid, 1000)

def send_message(c1,c2,gr, freq):
    symbols = FT8_encoder.pack_message(c1,c2,gr, freq)
    audio_out.create_ft8_wave(symbols)
    _ , t_remain = timers.time_in_cycle()
    time.sleep(t_remain)
    icom.setPTTON()
    audio_out.play_ft8_wave()
    icom.setPTTOFF()

def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), ClickHandler)
    server.serve_forever()

dump_config()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")
threading.Thread(target=liveRx.run).start()


    





