import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

from PyFT8.rx.cycle_manager import Cycle_manager
from PyFT8.rx.wsjtx_all_tailer import start_wsjtx_tailer
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws
import PyFT8.audio as audio
import threading
from PyFT8.rig.IcomCIV import IcomCIV
from PyFT8.sigspecs import FT8
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
            self.their_snr = int(msg_dict['snr'])
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
        tx_at_sec =  self.time_to_begin_tx(timers.tnow(), QSO.tx_cycle)
        c1, c2, grid_rpt = tx_msg.split()
        symbols = FT8_encoder.pack_message(c1, c2, grid_rpt)
        self.tx_ogm_to_priority_ui(c1, c2, grid_rpt, tx_at_sec)
        audio_data = audio.create_ft8_wave(symbols, f_base = config.txfreq)
        # doing tx threaded gives time for the tx_ogm to appear on the UI
        threading.Thread(target = self.do_tx, args=(audio_data, tx_at_sec, )).start()
       # self.do_tx(audio_data)
            
    def do_tx(self, audio_data, tx_at_sec):
        import PyFT8.timers as timers
        self.wait_for_sec(tx_at_sec)
        timers.sleep(0.05)
        timers.timedLog(f"[QSO.transmit] PTT ON", logfile = 'QSO.progress.log')
        rig.setPTTON()
        audio.play_data_to_soundcard(audio_data)
        rig.setPTTOFF()
        timers.timedLog(f"[QSO.transmit] PTT OFF", logfile = 'QSO.progress.log')

    def tx_ogm_to_priority_ui(self, c1, c2, grid_rpt, tx_at_sec):
        from PyFT8.comms_hub import config, send_to_ui_ws
        import PyFT8.timers as timers
        cycle_start_str = timers.strftime("%H%M%S", tx_at_sec);
        tx_ogm_dict = {'cyclestart_str':f"X_{cycle_start_str}", 'priority':True,
                    'snr':'-', 'freq':str(int(config.txfreq)), 'dt':' ',
                    'call_a':c1, 'call_b':c2, 'grid_rpt':grid_rpt}
        send_to_ui_ws("decode_dict", tx_ogm_dict)

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

def onDecode(decode_dict):
    import PyFT8.timers as timers
    from PyFT8.comms_hub import config, send_to_ui_ws
    if(decode_dict['call_a'] == config.myCall or decode_dict['call_b'] == config.myCall or 'rxfreq' in decode_dict or decode_dict['freq']==config.rxfreq or decode_dict['call_b']==QSO.their_call):
        decode_dict.update({'priority':True})
    send_to_ui_ws("decode_dict", decode_dict)
    if (decode_dict['call_a'] == config.myCall and decode_dict['call_b'] == QSO.their_call):
        QSO.progress(decode_dict)

def onOccupancy(spectrum_occupancy, spectrum_df, f0=0, f1=3500, bin_hz=10):
    from PyFT8.comms_hub import config, send_to_ui_ws
    import PyFT8.timers as timers
    import numpy as np

    occupancy_fine = spectrum_occupancy/np.max(spectrum_occupancy)
    n_out = int((f1-f0)/bin_hz)
    occupancy = np.zeros(n_out)
    for i in range(n_out):
        occupancy[i] = occupancy_fine[int((f0+bin_hz*i)/spectrum_df)]
    fs0, fs1 = 1000,1500
    bin0 = int((fs0-f0)/bin_hz)
    bin1 = int((fs1-f0)/bin_hz)
    clear_freq = fs0 + bin_hz*np.argmin(occupancy[bin0:bin1])
    occupancy = 10*np.log10(occupancy + 1e-12)
    occupancy = 1 + np.clip(occupancy, -40, 0) / 40
    
    config.update_clearest_txfreq(clear_freq)
    timers.timedLog(f"[onOccupancy] occupancy data received, set Tx to {config.txfreq}")
    send_to_ui_ws("freq_occ_array", {'histogram':occupancy.tolist()})

def process_UI_event(event):
    import PyFT8.timers as timers
    from PyFT8.comms_hub import send_to_ui_ws
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
        send_to_ui_ws("decode_dict", selected_message)
        if(selected_message['call_a'] == "CQ" or selected_message['call_a'] == config.myCall):
            QSO.progress(selected_message)
    if(topic == "ui.repeat-last"):
        QSO.rpt_cnt = 0
        QSO.progress({"repeat_tx":True})
    if(topic == "ui.call-cq"):
        QSO.clear()
        t = timers.tnow()
        i = int(((t-2) % 30)/15) 
        QSO.tx_cycle = ['odd','even'][i]
        QSO.transmit(f"CQ {config.myCall} {config.myGrid}")
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
    send_to_ui_ws("add_action_button", {'caption':'Call CQ', 'action':'call-cq', 'class':'button transmitting_button'})
    send_to_ui_ws("add_action_button", {'caption':'Repeat last', 'action':'repeat-last', 'class':'button transmitting_button'})
    for band in config.bands:
        send_to_ui_ws("add_action_button", {'caption':band['band_name'], 'action':f"set-band-{band['band_name']}-{band['band_freq']}", 'class':'button'})
    
def run():        
    cycle_manager = Cycle_manager(FT8, onDecode,
                              onOccupancy = onOccupancy,
                              max_iters = 30, max_stall = 8, max_ncheck = 33,
                              sync_score_thresh = 1.8, thread_PyFT8_decode_manager = True)
    start_UI("PyFT8_UI.html", process_UI_event)
    add_action_buttons()
    send_to_ui_ws("set_myCall", {'myCall':config.myCall})
    send_to_ui_ws("connect_pskr_mqtt", {'dummy':'dummy'})
    set_band_freq("set-band-20m-14.074")

    
run()
    
