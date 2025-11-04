
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import threading
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.rx.cycle_decoder import cycle_decoder
import PyFT8.tx.FT8_encoder as FT8_encoder
from PyFT8.comms_hub import config, send_to_ui_ws, start_UI

global QSO_date_on, QSO_time_on, QSO_date_off, QSO_time_off, QSO_call, their_grid, their_snr, my_snr, tx_message
global last_tx_messsage, repeat_counter, last_tx_complete_time
myCall = 'G1OJS'
myGrid = 'IO90'
myBand = '20m'
myFreq = '14.074'
my_snr = "+??"
their_grid = "????"
QSO_call = False
QSO_call_decoded = False # just for filtering duplicate decodes of QSO call
repeat_counter = 0
last_tx_messsage =''
last_tx_complete_time = 0
rig = IcomCIV()
testing_from_wsjtx = False

if testing_from_wsjtx:
    config.data.update({"input_device":["CABLE", "Output"]})
    config.data.update({"output_device":["CABLE", "Input"]})
    audio.find_audio_devices()

def onStart():
    global QSO_call_decoded
    QSO_call_decoded = False
    if(not QSO_call): # don't clear decodes during QSO
        send_to_ui_ws("clear_decodes", {})

def onDecode(decode):
    global QSO_call_decoded
    if(not decode): return
    decode_dict = decode['decode_dict']

    if(decode_dict['call_b'] == myCall or decode_dict['call_a'] == myCall or 'rxfreq' in decode_dict):
        decode_dict.update({'priority':True})
        
    if(not (decode_dict['call_b'] == QSO_call and QSO_call_decoded)):
        send_to_ui_ws("decode_dict", decode_dict)
    
    if (decode_dict['call_a'] == myCall and decode_dict['call_b'] == QSO_call):
        QSO_call_decoded = True
        reply_to_message(decode_dict)

def onOccupancy(occupancy, clear_freq):
    config.update_clearest_txfreq(clear_freq)
    send_to_ui_ws("freq_occ_array", {'histogram':occupancy.tolist()})

def process_UI_event(event):
    global QSO_call, last_tx_messsage, repeat_counter
    topic = event['topic']
    if(topic == "ui.clicked-message"):
        process_clicked_message(event)
    if(topic == "ui.repeat-last"):
        transmit_message(last_tx_message)
    if(topic == "ui.abort-qso"):
        QSO_call = False
    if(topic == "ui.call-cq"):
        repeat_counter = 0
        transmit_message(f"CQ {myCall} {myGrid}")

def process_clicked_message(selected_message):
    global QSO_call, last_tx_complete_time
    timers.timedLog(f"Clicked on message {selected_message}")
    config.txfreq = config.clearest_txfreq
    config.rxfreq = int(selected_message['freq'])
    last_tx_complete_time=0
    reply_to_message(selected_message)
    
def reply_to_message(decode_dict):
    global QSO_date_on, QSO_time_on,QSO_date_off, QSO_time_off, QSO_call, their_grid, their_snr, my_snr, tx_message
    call_a, call_b, grid_rpt, their_snr = decode_dict['call_a'], decode_dict['call_b'], decode_dict['grid_rpt'], decode_dict['snr']
    rx_message = f"{call_a} {call_b} {grid_rpt}"
    print(rx_message)
    if(call_a == "CQ"):
        print("CQ detected")
        QSO_call = call_b
        their_grid = grid_rpt
        QSO_date_on, QSO_time_on = timers.QSO_dnow_tnow()
        transmit_message(f"{call_b} {myCall} {myGrid}")
    if(call_a == myCall):
        QSO_call = call_b
        if(len(grid_rpt)>2):    
            if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
                my_snr = grid_rpt
                timers.timedLog(f"QSO reply received: {rx_message}", logfile = "QSO.log")
                transmit_message(f"{call_b} {myCall} R{their_snr:+03d}")
        if('73' in grid_rpt or 'RRR' in grid_rpt):
            timers.timedLog(f"QSO reply received: {rx_message}", logfile = "QSO.log")
            transmit_message(f"{call_b} {myCall} 73")
            QSO_date_off, QSO_time_off = timers.QSO_dnow_tnow()
            log_QSO()
            QSO_call = False

def transmit_message(msg):
    print(f"In transmit msg {msg}")
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

def log_QSO():
    import PyFT8.logging as logging
    logging.append_qso("test.adi",{
    'gridsquare':their_grid, 'mode':'FT8','operator':myCall,
    'rst_sent':their_snr, 'rst_rcvd':my_snr,
    'qso_date':QSO_date_on, 'time_on':QSO_time_on,
    'qso_date_off':QSO_date_off, 'time_off':QSO_time_off,
    'band':myBand, 'freq':myFreq,
    'station_callsign':myCall, 'my_gridsquare':myGrid})


threading.Thread(target=cycle_decoder, kwargs=({'onStart':onStart, 'onDecode':onDecode, 'onOccupancy':onOccupancy})).start()
start_UI(process_UI_event)

    
