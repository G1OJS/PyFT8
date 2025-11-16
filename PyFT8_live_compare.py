import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_decoder import cycle_decoder
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import PyFT8.timers as timers
import threading
from PyFT8.rig.IcomCIV import IcomCIV
rig = IcomCIV()

def wsjtx_tailer():
    def follow(path):
        with open(path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    timers.sleep(0.2)
                    continue
                yield line.strip()
    for line in follow(r"C:\Users\drala\AppData\Local\WSJT-X\ALL.txt"):
        ls = line.split()
       # decode_dict = {'cyclestart_str':ls[0].split("_")[1],'call_a':ls[7], 'call_b':ls[8]}
        decode_dict = {'cyclestart_str':ls[0],'call_a':ls[7], 'call_b':ls[8]}
        if(len(ls)>9): decode_dict.update({'grid_rpt':ls[9]})
        decode = {'decode_dict':decode_dict,'all_txt_line':line}
        on_wsjtx_decode(decode)

def on_wsjtx_decode(decode):
    decode_dict = decode['decode_dict']
    decode_dict.update({'wsjtx':True})
    send_to_ui_ws("decode_dict", decode_dict)

def onDecode(decode):
    decode_dict = decode['decode_dict']
    decode_dict.update({'wsjtx':False})
    send_to_ui_ws("decode_dict", decode_dict)

def process_UI_event(event):
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
    threading.Thread(target=wsjtx_tailer).start()
    threading.Thread(target=cycle_decoder, kwargs=({'onDecode':onDecode, 'score_thresh':1000000})).start()
    start_UI("PyFT8_live_compare.html", process_UI_event)
    add_band_buttons()

run()
    

