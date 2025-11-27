import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.wsjtx_all_tailer import start_wsjtx_tailer

from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import threading
from PyFT8.rig.IcomCIV import IcomCIV
rig = IcomCIV()

class QSO:
    def __init__(self):
        self.tx_cycle = False
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

    def tx_cycle_from_clicked_message(self, selected_message):
        return 'odd' if (selected_message['cyclestart_str'][-2:] in ['00','30']) else 'even'

    def tx_cycle_from_click_time(self, t_click):
        i = int(((t_click+7.5) % 30)/15)
        tx_cycle = ['even','odd'][i]
        return tx_cycle

    def time_to_begin_tx(self, tnow, tx_cycle):
        max_immediate = 15 - 12.6
        t = tnow + (15 if tx_cycle == 'odd' else 0)
        t = t %30
        twait = 30 - t
        if(twait > 30-max_immediate): twait=0
        tbegin = twait + tnow
        import PyFT8.timers as timers
        timers.timedLog(f"[QSO.transmit] time_to_begin_tx calculated {tbegin} with inputs {t}, {tx_cycle}", logfile = 'QSO.progress.log')
        return tbegin

    def wait_for_sec(self, sec):
        import PyFT8.timers as timers
        twait = sec - timers.tnow()
        if(twait > 0):
            timers.timedLog(f"[QSO.transmit] Waiting for {self.tx_cycle} cycle start ({twait:4.1f}s)", logfile = 'QSO.progress.log')
            timers.sleep(twait)

    def progress(self, msg_dict):
        # work out *what* to transmit. *when* is worked out in transmit below
        import PyFT8.timers as timers
        timers.timedLog(f"[QSO.progress] QSO.tx_cycle is {QSO.tx_cycle}", logfile = 'QSO.progress.log')
        if("repeat_tx" in msg_dict):
            if(self.tx_msg and self.tx_cycle):
                self.transmit(self.tx_msg)
            return

        call_a, their_call, grid_rpt = msg_dict['call_a'], msg_dict['call_b'], msg_dict['grid_rpt']
        if(call_a == "CQ" or call_a == config.myCall):
            self.their_call = their_call
            self.their_snr = msg_dict['snr']
            self.date, self.time_on = timers.QSO_dnow_tnow()

        if("+" not in grid_rpt and "-" not in grid_rpt and "73" not in grid_rpt):
            self.their_grid = grid_rpt
            
        timers.timedLog(f"[QSO.progress] Progress QSO with {self.their_call}", logfile = 'QSO.progress.log')
        timers.timedLog(f"[QSO.progress] msg_dict = {msg_dict}", logfile = 'QSO.progress.log')
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
            self.transmit(f"{self.their_call} {config.myCall} {config.myGrid}")
            return

        if(call_a == config.myCall):
            self.transmit(f"{self.their_call} {config.myCall} {QSO.their_snr:+03d}")
            return
        
    def transmit(self, tx_msg):
        import PyFT8.tx.FT8_encoder as FT8_encoder
        import PyFT8.timers as timers
        self.rpt_cnt = self.rpt_cnt + 1 if(tx_msg == self.tx_msg ) else 0
        if(self.rpt_cnt >= 5):
            timers.timedLog("[QSO.transmit] Skip, repeat count too high", logfile = 'QSO.progress.log')
            return
        if(not tx_msg):
            timers.timedLog("[QSO.transmit] Skip, no message", logfile = 'QSO.progress.log')
            return
        self.tx_msg = tx_msg
        timers.timedLog(f"[QSO.transmit] Send message: ({self.rpt_cnt}) {tx_msg}", logfile = 'QSO.progress.log')
        c1, c2, grid_rpt = tx_msg.split()
        symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
        audio_data = audio.create_ft8_wave(symbols, f_base = config.txfreq)
        threading.Thread(target = self.do_tx, args=(audio_data, )).start()
            
    def do_tx(self, audio_data):
        import PyFT8.timers as timers
        tx_at_sec =  self.time_to_begin_tx(timers.tnow(), QSO.tx_cycle)
        self.wait_for_sec(tx_at_sec)
        self.tx_ogm_to_priority_ui(self.tx_msg)
        timers.sleep(0.05)
        timers.timedLog(f"[QSO.transmit] PTT ON", logfile = 'QSO.progress.log')
        rig.setPTTON()
        audio.play_data_to_soundcard(audio_data)
        rig.setPTTOFF()
        timers.timedLog(f"[QSO.transmit] PTT OFF", logfile = 'QSO.progress.log')

    def tx_ogm_to_priority_ui(self, msg):
        from PyFT8.comms_hub import config, send_to_ui_ws
        import PyFT8.timers as timers
        t_elapsed = timers.tnow() % 15
        msg_parts = msg.split()
        tx_ogm_dict = {'cyclestart_str':f"X_{timers.tnow_str()}", 'priority':True,
                    'snr':'+00', 'freq':str(int(config.txfreq)), 'dt':f"{t_elapsed:3.1f}",
                    'call_a':msg_parts[0], 'call_b':msg_parts[1], 'grid_rpt':msg_parts[2]}
        send_to_ui_ws("msg", tx_ogm_dict)

    def log(self):
        import PyFT8.logging as logging
        log_dict = {'call':self.their_call, 'gridsquare':self.their_grid, 'mode':'FT8',
        'operator':config.myCall, 'station_callsign':config.myCall, 'my_gridsquare':config.myGrid, 
        'rst_sent':f"{int(self.their_snr):+03d}", 'rst_rcvd':f"{int(self.my_snr):+03d}", 
        'qso_date':self.date, 'time_on':self.time_on,
        'qso_date_off':self.date_off, 'time_off':self.time_off,
        'band':config.myBand, 'freq':config.myFreq, 'comment':'PyFT8' }
        import PyFT8.timers as timers
        timers.timedLog("[QSO.log] send to ADIF {log_dict}", logfile = 'QSO.progress.log')
        logging.append_qso("PyFT8.adi", log_dict)

QSO = QSO()

def onDecode(candidate):
    import PyFT8.timers as timers
    from PyFT8.comms_hub import config, send_to_ui_ws
    decode_dict = candidate.decode_dict
    if(decode_dict['call_a'] == config.myCall or decode_dict['call_b'] == config.myCall or 'rxfreq' in decode_dict or decode_dict['freq']==config.rxfreq or decode_dict['call_b']==QSO.their_call):
        decode_dict.update({'priority':True})
    send_to_ui_ws("decode_dict", decode_dict)
    if (decode_dict['call_a'] == config.myCall and decode_dict['call_b'] == QSO.their_call):
        QSO.progress(decode_dict)

def onOccupancy(occupancy, clear_freq):
    from PyFT8.comms_hub import config, send_to_ui_ws
    import PyFT8.timers as timers
    config.update_clearest_txfreq(clear_freq)
    timers.timedLog(f"[onOccupancy] occupancy data received, set Tx to {config.txfreq}")
    send_to_ui_ws("freq_occ_array", {'histogram':occupancy.tolist()})

def process_UI_event(event):
    import PyFT8.timers as timers
    global QSO
    topic = event['topic']
    if(topic == "ui.clicked-message"):
        from PyFT8.comms_hub import send_to_ui_ws
        selected_message = event
        timers.timedLog(f"[process_UI_event] Clicked on message {selected_message}")
        config.txfreq = config.clearest_txfreq
        config.rxfreq = int(selected_message['freq'])
        timers.timedLog(f"[process_UI_event] Set Rx freq to {config.rxfreq}", logfile = 'QSO.progress.log')
        QSO.tx_cycle = QSO.tx_cycle_from_clicked_message(selected_message)
        selected_message.update({'priority':True})
        send_to_ui_ws("msg", selected_message)
        if(selected_message['call_a'] == "CQ" or selected_message['call_a'] == config.myCall):
            QSO.progress(selected_message)
    if(topic == "ui.repeat-last"):
        QSO.rpt_cnt = 0
        QSO.progress({"repeat_tx":True})
    if(topic == "ui.call-cq"):
        QSO.clear()
        QSO.tx_cycle = QSO.tx_cycle_from_click_time(timers.tnow())
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
    cycle_manager = Cycle_manager(None if config.decoder == 'wsjtx' else onDecode, onOccupancy, 
                              max_iters = 60, max_stall = 8, max_ncheck = 35,
                              sync_score_thresh = 2.0, min_sd = 1.7, max_delay = 2,
                              max_parallel_decodes = 100)
    if(config.decoder == 'wsjtx') : start_wsjtx_tailer(onDecode)
    start_UI("PyFT8_tcvr_UI.html", process_UI_event)
    add_band_buttons()
    send_to_ui_ws("set_myCall", {'myCall':config.myCall})
run()
    
