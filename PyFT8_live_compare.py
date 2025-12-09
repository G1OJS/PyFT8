import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.wsjtx_all_tailer import start_wsjtx_tailer
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import PyFT8.timers as timers
import threading
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.sigspecs import FT8

rig = IcomCIV()

global PyFT8_has_decodes
PyFT8_has_decodes = False
import os
if(os.path.exists('decodes.log')):
    os.remove('decodes.log')
    
def on_wsjtx_decode(decode_dict):
    if(not PyFT8_has_decodes): return
    decode_dict.update({'source':'WSJTX'})
    send_to_ui_ws("decode_dict", decode_dict)

def onDecode(candidate):
    global PyFT8_has_decodes
    PyFT8_has_decodes = True
    decode_dict = candidate.decode_result
    decode_dict.update({'source':'PyFT8'})
    send_to_ui_ws("decode_dict", decode_dict)

def process_UI_event(event):
    topic = event['topic']
    if("set-band" in topic):
        set_band_freq(topic)

def set_band_freq(action):
        fields = action.split("-")
        config.myFreq = float(fields[3])
        config.myBand = fields[2]
        rig.setFreqHz(int(config.myFreq * 1000000))
        rig.setMode(md="USB", dat = True, filIdx = 1)
        with open("PyFT8_MHz.txt","w") as f:
            f.write(str(config.myFreq))
        send_to_ui_ws("set_band", {"band":config.myBand})
        
def add_action_buttons():
    from PyFT8.comms_hub import config, send_to_ui_ws
    for band in config.bands:
        send_to_ui_ws("add_action_button", {'caption':band['band_name'], 'action':f"set-band-{band['band_name']}-{band['band_freq']}", 'class':'button'})

def run():
    start_wsjtx_tailer(on_wsjtx_decode)
    cycle_manager = Cycle_manager(FT8, onDecode, onOccupancy = None, 
                              max_iters = 35, max_stall = 8, max_ncheck = 35,
                              sync_score_thresh = 1.6)
    start_UI("PyFT8_live_compare.html", process_UI_event)
    add_action_buttons()
    set_band_freq("set-band-20m-14.074")

    cycle_manager.decode_manager()

run()
    

