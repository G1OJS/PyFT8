import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.wsjtx_all_tailer import start_wsjtx_tailer
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import PyFT8.timers as timers
import threading
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.signaldefs import FT8

rig = IcomCIV()

global PyFT8_has_decodes
PyFT8_has_decodes = False
import os
if(os.path.exists('decodes.log')):
    os.remove('decodes.log')
    
def on_wsjtx_decode(decode):
    if(not PyFT8_has_decodes): return
    decode_result = decode['decode_dict']
    decode_result.update({'source':'WSJTX'})
    send_to_ui_ws("decode_dict", decode_result)

def onDecode(candidate):
    global PyFT8_has_decodes
    PyFT8_has_decodes = True
    decode_result = candidate.decode_result
    decode_result.update({'source':'PyFT8'})
    send_to_ui_ws("decode_dict", decode_result)

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
    cycle_manager = Cycle_manager(FT8, None if config.decoder == 'wsjtx' else onDecode,
                              onOccupancy = None, verbose = True,
                              max_iters = 60, max_stall = 8, max_ncheck = 33,
                              sync_score_thresh = 2.3, llr_sd_thresh = 1.8)
    start_UI("PyFT8_live_compare.html", process_UI_event)
    add_band_buttons()

run()
    

