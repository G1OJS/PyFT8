import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_decoder import cycle_decoder
from PyFT8.comms_hub import config, start_UI
import PyFT8.audio as audio
import threading
from PyFT8.rig.IcomCIV import IcomCIV
rig = IcomCIV()

class QSO:
    def __init__(self):
        self.cycle = 'next'
        self.tx_msg = False
        self.rpt_cnt = 0
        self.my_snr = False
        self.their_grid = False
        self.their_call = False
        self.their_snr = False
        self.time_on = False
        self.time_off = False
        self.date = False
        self.date_off = False

    def clear(self):
        self.cycle = 'next'
        self.tx_msg = False
        self.my_snr = False
        self.their_grid = False
        self.their_call = False
        self.time_on = False
        self.time_off = False
        self.date = False
        self.date_off = False

    def progress(self, msg_dict, immediate = False):
        import PyFT8.timers as timers
        timers.timedLog(f"[QSO.progress] QSO.cycle is {QSO.cycle}")
        if("repeat_tx" in msg_dict):
            if(self.tx_msg):
                self.transmit(self.tx_msg)
            else:
                timers.timedLog(f"[QSO.progress] No message")
            return

        call_a, their_call, grid_rpt = msg_dict['call_a'], msg_dict['call_b'], msg_dict['grid_rpt']
        if(call_a == "CQ" or call_a == config.myCall):
            self.their_call = their_call
            self.their_snr = msg_dict['snr']
            self.date, self.time_on = timers.QSO_dnow_tnow()

        if("+" not in grid_rpt and "-" not in grid_rpt and "73" not in grid_rpt):
            self.their_grid = grid_rpt
            
        timers.timedLog(f"[QSO] Progress QSO with {self.their_call}")
        timers.timedLog(f"[QSO] msg_dict = {msg_dict}")
        if('73' in grid_rpt or 'R' in grid_rpt):
            reply = '73'
            if (grid_rpt[-4]=='R' and grid_rpt[-3] !='R'):
                reply = 'RR73'
            self.transmit(f"{self.their_call} {config.myCall} {reply}")
            self.date_off, self.time_off = timers.QSO_dnow_tnow()
            self.log()
            self.clear()
            return

        if(len(grid_rpt)>=3):
            if(grid_rpt[-3]=="+" or grid_rpt[-3]=="-"):
                self.transmit(f"{self.their_call} {config.myCall} R{QSO.their_snr:+03d}")
                self.my_snr = grid_rpt[-3:]
                return

        if(call_a == "CQ"):
            self.transmit(f"{self.their_call} {config.myCall} {config.myGrid}", immediate = immediate)
            return

        if(call_a == config.myCall):
            self.transmit(f"{self.their_call} {config.myCall} {QSO.their_snr:+03d}", immediate = immediate)
            return
        
    def transmit(self, tx_msg, immediate = False):
        import PyFT8.tx.FT8_encoder as FT8_encoder
        import PyFT8.timers as timers
        self.rpt_cnt = self.rpt_cnt + 1 if(tx_msg == self.tx_msg ) else 0
        if(self.rpt_cnt >= 5):
            timers.timedLog("[QSO.transmit] Skip, repeat count too high")
            return
        self.tx_msg = tx_msg
        timers.timedLog(f"[QSO.transmit] Send message: ({self.rpt_cnt}) {tx_msg}")
        c1, c2, grid_rpt = tx_msg.split()
        symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
        audio_data = audio.create_ft8_wave(symbols, f_base = config.txfreq)
        if(not (immediate and self.cycle == timers.odd_even_now(from_click = True) ) ):
            t_elapsed, t_remaining = timers.time_in_cycle(self.cycle)
            if(t_elapsed > 2 or t_elapsed <0):
                timers.timedLog(f"[QSO.transmit] Waiting for {self.cycle} cycle start ({t_remaining:4.1f}s)")
                timers.sleep(t_remaining)
        self.decode_to_priority_ui(self.tx_msg)
        timers.sleep(0.1)
        threading.Thread(target = self.do_tx, args=(audio_data,)).start()
            
    def do_tx(self, audio_data):
        import PyFT8.timers as timers
        timers.timedLog(f"[QSO.transmit] PTT ON")
        rig.setPTTON()
        audio.play_data_to_soundcard(audio_data)
        rig.setPTTOFF()
        timers.timedLog(f"[QSO.transmit] PTT OFF")

    def decode_to_priority_ui(self, msg):
        from PyFT8.comms_hub import config, send_to_ui_ws
        import PyFT8.timers as timers
        t_elapsed, t_remaining = timers.time_in_cycle()
        msg_parts = msg.split()
        decode_to_priority_ui_dict = {'cyclestart_str':f"X_{timers.tnow_str()}", 'priority':True,
                    'snr':'+00', 'freq':str(int(config.txfreq)), 'dt':f"{t_elapsed:3.1f}",
                    'call_a':msg_parts[0], 'call_b':msg_parts[1], 'grid_rpt':msg_parts[2]}
        send_to_ui_ws("msg", decode_to_priority_ui_dict)

    def log(self):
        import PyFT8.logging as logging
        log_dict = {'call':self.their_call, 'gridsquare':self.their_grid, 'mode':'FT8',
        'operator':config.myCall, 'station_callsign':config.myCall, 'my_gridsquare':config.myGrid, 
        'rst_sent':f"{int(self.their_snr):+03d}", 'rst_rcvd':f"{int(self.my_snr):+03d}", 
        'qso_date':self.date, 'time_on':self.time_on,
        'qso_date_off':self.date_off, 'time_off':self.time_off,
        'band':config.myBand, 'freq':config.myFreq, 'comment':'PyFT8' }
        import PyFT8.timers as timers
        timers.timedLog("[QSO] send to ADIF {log_dict}")
        logging.append_qso("PyFT8.adi", log_dict)

QSO = QSO()
decode_filter = False

def onStart():
    from PyFT8.comms_hub import send_to_ui_ws
    global decode_filter
    send_to_ui_ws("clear_decodes", {})
    decode_filter = []

def onDecode(decode):
    import PyFT8.timers as timers
    from PyFT8.comms_hub import config, send_to_ui_ws
    if(not decode):
        return
    decode_dict = decode['decode_dict']
    key = f"{decode_dict['call_a']}{decode_dict['call_b']}"
    if(key in decode_filter):
        timers.timedLog(f"[QSO] Reject duplicate decode {decode_dict}")
        return
    decode_filter.append(key)
    if(decode_dict['call_a'] == config.myCall or decode_dict['call_b'] == config.myCall or 'rxfreq' in decode_dict):
        decode_dict.update({'priority':True})
    send_to_ui_ws("decode_dict", decode_dict)
    if (decode_dict['call_a'] == config.myCall and decode_dict['call_b'] == QSO.their_call):
        QSO.progress(decode_dict)

def onOccupancy(occupancy, clear_freq):
    from PyFT8.comms_hub import config, send_to_ui_ws
    config.update_clearest_txfreq(clear_freq)
    send_to_ui_ws("freq_occ_array", {'histogram':occupancy.tolist()})

def process_UI_event(event):
    import PyFT8.timers as timers
    global QSO
    topic = event['topic']
    if(topic == "ui.clicked-message"):
        from PyFT8.comms_hub import send_to_ui_ws
        selected_message = event
        timers.timedLog(f"Clicked on message {selected_message}")
        config.txfreq = config.clearest_txfreq
        config.rxfreq = int(selected_message['freq'])
        QSO.cycle = 'odd' if (selected_message['cyclestart_str'][-2:] in ['00','30']) else 'even'
        selected_message.update({'priority':True})
        send_to_ui_ws("msg", selected_message)
        if(selected_message['call_a'] == "CQ" or selected_message['call_a'] == config.myCall):
            QSO.progress(selected_message, immediate = True)
    if(topic == "ui.repeat-last"):
        QSO.rpt_cnt = 0
        QSO.progress({"repeat_tx":True})
    if(topic == "ui.call-cq"):
        QSO.clear()
        QSO.cycle = timers.odd_even_now(from_click = True)
        QSO.transmit(f"CQ {config.myCall} {config.myGrid}")
    if("set-band" in topic):
        fields = topic.split("-")
        config.myFreq = float(fields[3])
        config.myBand = fields[2]
        rig.setFreqHz(int(config.myFreq * 1000000))
        rig.setMode(md="USB", dat = True, filIdx = 1)
        with open("PyFT8_MHz.txt","w") as f:
            f.write(str(config.myFreq))
        
def add_band_buttons():
    from PyFT8.comms_hub import config, send_to_ui_ws
    for band in config.bands:
        send_to_ui_ws("add_band_button", {'band_name':band['band_name'], 'band_freq':band['band_freq']})

def run():        
    # if testing_from_wsjtx:
    #config.data.update({"input_device":["CABLE", "Output"]})
    #config.data.update({"output_device":["CABLE", "Input"]})
    #audio.find_audio_devices()
    
    threading.Thread(target=cycle_decoder, kwargs=({'onStart':onStart, 'onDecode':onDecode, 'onOccupancy':onOccupancy, 'score_thresh':1000000})).start()
    start_UI(process_UI_event)
    add_band_buttons()

run()
    
#import PyFT8.timers as timers
#config.data.update({"output_device":["CABLE", "Input"]})
#audio.find_audio_devices()
#QSO.cycle = timers.odd_even_now(from_click = True)
#QSO.transmit("N1JFU EA6EE R-07")
