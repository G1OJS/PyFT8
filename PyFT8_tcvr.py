
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import threading
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.rx.FT8_demodulator import cyclic_demodulator
import PyFT8.tx.FT8_encoder as FT8_encoder
from PyFT8.comms_hub import config, send_to_ui_ws, start_UI

myCall = 'G1OJS'
myGrid = 'IO90'
global QSO_call, last_tx_messsage, repeat_counter, last_tx_complete_time
QSO_call = False
repeat_counter = 0
last_tx_messsage =''
last_tx_complete_time = 0
rig = IcomCIV()
testing_from_wsjtx = False

if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    config.data.update({"output_device":["CABLE", "Input"]})
    audio.find_audio_devices()

def process_clicked_message(selected_message):
    timers.timedLog(f"Clicked on message {selected_message}")
    config.txfreq = config.clearest_txfreq
    global QSO_call, last_tx_complete_time
    config.rxfreq = int(selected_message['freq'])
    last_tx_complete_time=0
    reply_to_message(selected_message)

def process_decode(decode):
    if(not decode): return
    decode_dict = decode['decode_dict']
    if(decode_dict['call_b'] == myCall or decode_dict['call_a'] == myCall or 'rxfreq' in decode_dict):
        decode_dict.update({'priority':True})        
    send_to_ui_ws("decode_dict", decode_dict)
    if (decode_dict['call_a'] == myCall and decode_dict['call_b'] == QSO_call):
        reply_to_message(decode_dict)
        
def reply_to_message(decode_dict):
    global QSO_call, tx_message
    call_a, call_b, grid_rpt, their_snr = decode_dict['call_a'], decode_dict['call_b'], decode_dict['grid_rpt'], decode_dict['snr']
    rx_message = f"{call_a} {call_b} {grid_rpt}"
    if(call_a == "CQ"):
        QSO_call = call_b
        transmit_message(f"{call_b} {myCall} {myGrid}")
    if(call_a == myCall):
        QSO_call = call_b
        if(len(grid_rpt)>2):    
            if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
                timers.timedLog(f"QSO reply received: {rx_message}", logfile = "QSO.log")
                transmit_message(f"{call_b} {myCall} R{their_snr:+03d}")
        if('73' in grid_rpt or 'RRR' in grid_rpt):
            timers.timedLog(f"QSO reply received: {rx_message}", logfile = "QSO.log")
            transmit_message(f"{call_b} {myCall} 73")
            QSO_call = ''

def transmit_message(msg):
    global QSO_call, repeat_counter, last_tx_complete_time, last_tx_messsage
    if(not msg):
        timers.timedLog("QSO transmit skip, no message to transmit", logfile = "QSO.log")
        return
    if(last_tx_complete_time > timers.tnow() -7):
        timers.timedLog("QSO transmit skip, too close to last transmit", logfile = "QSO.log")
        return        
    repeat_counter = repeat_counter + 1 if( msg == last_tx_messsage ) else 0
    if(repeat_counter >= 3):
        timers.timedLog("QSO transmit skip, repeat count too high", logfile = "QSO.log")
        return
    last_tx_messsage = msg
    timers.timedLog(f"Send message: ({repeat_counter}) {msg}", logfile = "QSO.log")
    c1, c2, grid_rpt = msg.split()
    symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
    audio_data = audio.create_ft8_wave(symbols, f_base = config.txfreq)
    t_elapsed, t_remaining = timers.time_in_cycle()
    if(t_remaining < 3):
        timers.timedLog("QSO transmit waiting for cycle start", logfile = "QSO.log")
        timers.sleep(t_remaining)
    timers.timedLog(f"PTT ON", logfile = "QSO.log")
    rig.setPTTON()
    audio.play_data_to_soundcard(audio_data)
    rig.setPTTOFF()
    last_tx_complete_time = timers.tnow()
    timers.timedLog(f"PTT OFF", logfile = "QSO.log")

def clear_decodes():
    send_to_ui_ws("clear_decodes", {})
    
threading.Thread(target=cyclic_demodulator, kwargs=({'onStart':clear_decodes, 'onDecode':process_decode})).start()
start_UI(process_clicked_message)

    
