import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import time
import webbrowser
import subprocess

from PyFT8.tx import FT8_encoder
from PyFT8.rig.IcomCIV import IcomCIV
import PyFT8.tx.audio_out as audio_out
import PyFT8.timers as timers
import json
icom = IcomCIV()
cycle_length = 15
myCall = 'G1OJS'
myGrid = 'IO90'

global abort_qso
abort_qso = False

global config
config = {'txFreq':2250, 'rxFreq':1971 }
def dump_config():
    with open("config.json", "w") as f:
        json.dump(config, f)
dump_config()
from PyFT8.rx import liveRx

class ClickHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/select_"):
            threading.Thread(target=process_click_content, args=(self.path,)).start()  
        super().do_GET()
    def log_message(self, format, *args):
        return


class ClickHandler_(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/select_"):
            threading.Thread(target=process_click_content, args=(self.path,)).start()  
        super().do_GET()

def process_click_content(clickdata):
    global config
    text = clickdata.strip("/").replace("select_", "").replace(".txt", "").replace('%20',' ')
    rxFreq, callsign = text.split("_")
    config['rxFreq'] = int(rxFreq);
    print(f"Set Rx freq to {config['rxFreq']}")
    dump_config()
    clear_rxWindow()
    if(callsign != 'None'):
        initiate_qso(str(callsign))

def clear_rxWindow():
    with open("rxFreq_data.json", "w") as f:
        f.write("")

def get_rxFreqMessages(from_call = None):
    with open("rxFreq_data.json", "r") as f:
        s = f.readline()
        if(s):
            if(not from_call or len(eval(s)) == 1): return eval(s)[0]['grid_rpt']
            decode = next((item for item in eval(s) if item["call_b"] == from_call), None)
            if(decode): return decode['grid_rpt']  

def initiate_qso(callsign, wait_for_next = False):
    _ , t_remain = timers.time_in_cycle()
    clear_rxWindow()
    if(t_remain < 13):
        timers.timedLog(f"Not enough time: t_remain = {t_remain} seconds")
        time.sleep(t_remain+15)
    timers.timedLog(f"Initiate QSO with {callsign}")
    while True:
        send_message(callsign, myCall, myGrid, int(config['txFreq']), wait_for_next = wait_for_next)
        wait_for_next = True
        their_reply = get_rxFreqMessages(callsign)
        if(not their_reply): continue
        if(their_reply[-3:].isnumeric): break
    while True:
        their_snr = their_reply['snr']
        send_message(callsign, myCall, f"R{their_snr:+03d}", int(config['txFreq']), wait_for_next = True)
        if('73' in get_rxFreqMessages(callsign)): break
    send_message(callsign, myCall, 'RR73', int(config['txFreq']), wait_for_next = True)
    
def send_message(c1,c2,gr, freq, wait_for_next = True):
    timers.timedLog(f"Sending: {c1} {c2} {gr}")
    symbols = FT8_encoder.pack_message(c1,c2,gr)
    audio_out.create_ft8_wave(symbols, f_base = freq)
    if(wait_for_next):
        _ , t_remain = timers.time_in_cycle()
        time.sleep(t_remain)
    icom.setPTTON()
    audio_out.play_ft8_wave()
    icom.setPTTOFF()

def start_UI_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), ClickHandler)
    server.serve_forever()

def delete_file(file):
    if os.path.exists(file):
        os.remove(file)
        
delete_file("rxFreq_data.json")
delete_file("data.json")
delete_file("config.json")
dump_config()
threading.Thread(target=liveRx.run).start()
threading.Thread(target=start_UI_server, daemon=True).start()
webbrowser.open("http://localhost:8080/UI.html")

#send_message("CQ","G1OJS","IO90", 1000)

#send_message("X1XXX","G1OJS","+03", 1000)
#send_message("X1XXX","G1OJS","-08", 1000)

#send_message("X1XXX","G1OJS","R+08", 1000)
#send_message("X1XXX","G1OJS","R-08", 1000)

#send_message("X1XXX","G1OJS","RRR", 1000)

#send_message("X1XXX","G1OJS","RR73", 1000)

#send_message("X1XXX","G1OJS","73", 1000)
#send_message("X1XXX","G1O","73", 1000)
    
