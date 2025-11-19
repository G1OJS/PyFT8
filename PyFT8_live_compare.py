import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_decoder import Cycle_decoder
from PyFT8.rx.wsjtx_all_tailer import start_wsjtx_tailer
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import PyFT8.timers as timers
import threading
from PyFT8.rig.IcomCIV import IcomCIV

rig = IcomCIV()

global PyFT8_has_decodes, wsjtx_has_decodes
PyFT8_has_decodes = False
wsjtx_has_decodes = False

def on_wsjtx_decode(decode):
    global wsjtx_has_decodes
    wsjtx_has_decodes = True
    if(not PyFT8_has_decodes): return
    decode_dict = decode['decode_dict']
    decode_dict.update({'wsjtx':True})
    send_to_ui_ws("decode_dict", decode_dict)

def onDecode(decode):
    global PyFT8_has_decodes, wsjtx_has_decodes
    if(not PyFT8_has_decodes or not wsjtx_has_decodes):
        wsjtx_has_decodes = False
        PyFT8_has_decodes = True
        return
    decode_dict = decode['decode_dict']
    decode_dict.update({'wsjtx':False})
    send_to_ui_ws("decode_dict", decode_dict)

def process_UI_event(event):
    topic = event['topic']
    if("set-band" in topic):
        fields = topic.split("-")
        config.myFreq = float(fields[3])
        config.myBand = fields[2]
        rig.setFreqHz(int(config.myFreq * 1000000))
        rig.setMode(md="USB", dat = True, filIdx = 1)
        with open("PyFT8_MHz.txt","w") as f:
            f.write(str(config.myFreq))
        
def add_band_buttons():
    for band in config.bands:
        send_to_ui_ws("add_band_button", {'band_name':band['band_name'], 'band_freq':band['band_freq']})

def run():
    start_wsjtx_tailer(on_wsjtx_decode)
    cd = Cycle_decoder(onDecode, onOccupancy = None, prioritise_rxfreq = False)
    start_UI("PyFT8_live_compare.html", process_UI_event)
    add_band_buttons()

run()
    

