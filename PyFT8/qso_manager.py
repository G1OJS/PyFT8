import threading
import time
from PyFT8.time_utils import time_utils
from PyFT8.transmitter import get_ft8_symbols, symbols_to_audio_bytes
MAX_TX_START_CYCLETIME = 3

class QSO_manager:
    def __init__(self, myCall, myGrid, console_print, transmit_audio_data_bytes, rig, wf_data, adif_logging):
        self.transmit_audio_data_bytes = transmit_audio_data_bytes
        self.qso_info = {'operator':myCall, 'station_callsign':myCall, 'my_gridsquare':myGrid, 'mode':'FT8', 
                        'call':None, 'gridsquare':None, 'rst_sent':None, 'rst_rcvd': None, 
                        'qso_date':None, 'qso_date_off':None, 'time_on':None, 'time_off':None,
                        'band':None, 'freq':None}
        self.adif_logging = adif_logging
        self.qso_active = False
        self.tx_payload = None
        self.tx_cycle = 0
        self.wf_data = wf_data
        self.console_print = console_print
        self.rig = rig
        self.band_info = {'current_band': None, 'fMHz':0, 'time_set':0}
        self.myCall, self.myGrid = myCall, myGrid
        self.tx_freq = 750
        self.console_print(f"[PyFT8] QSO handler started for {self.myCall}")
        threading.Thread(target = self._transmit_daemon, daemon = True).start()

    def get_band_info(self):
        return self.band_info

    def on_click(self, clickargs):
        btn_action = clickargs['action']
        if btn_action in ['MESSAGE_CLICK','CQ'] and self.band_info['current_band'] is None:
            self.console_print("Please select a band before transmitting", color = 'red')
            return
        
        if btn_action == "CQ":            
            self.tx_cycle = time_utils.odd_even()
            if time_utils.cycle_time() > MAX_TX_START_CYCLETIME:
                self.tx_cycle = 1 - self.tx_cycle 
            self._set_tx_payload(f"CQ {self.myCall} {self.myGrid[:4]}")
        if btn_action == "RPT_LAST":
            self.tx_payload = self.last_tx_payload
        if btn_action == "TX_OFF":
            self.console_print("[PyFT8] Set PTT Off")
            self.rig.ptt_off()
            self.tx_payload = None
            self.qso_active = False
        if(btn_action == 'SET_BAND'):
            current_band, freqMHz = clickargs['band'], clickargs['freq']
            self.band_info = {'current_band':current_band, 'fMHz':freqMHz, 'time_set':time_utils.time()}
            self.rig.set_freq_Hz(int(1000000*float(self.band_info['fMHz'])))
            self.console_print(f"[PyFT8] Set band: {self.band_info['current_band']} {self.band_info['fMHz']}")

        if btn_action == "MESSAGE_CLICK":
            message = clickargs['message']
            message_type = message['message_type']
            new_qso_info = message['new_qso_info']
            reply = ""
            
            if message_type == "CQ" or message_type == "to_me":
                if not self.qso_active or message_type == "CQ":
                    gmt = time.gmtime()
                    self.qso_info.update({'call':new_qso_info['call'],
                                         'time_on': time.strftime("%H%M%S", gmt), 'qso_date':time.strftime("%Y%m%d", gmt),
                                         'band':self.band_info['current_band'], 'freq':self.band_info['fMHz'],
                                         'rst_sent':new_qso_info['rst_sent'] })
                    self.tx_cycle = new_qso_info['my_tx_cycle']
                    self.tx_freq = self._find_clear_freq(self.band_info['current_band'])
                    self.qso_active = True

            grid_rpt = new_qso_info['grid_rpt']
            if any([m for m in ['+','-'] if m in grid_rpt]): # grid_rpt == rpt
                self.qso_info.update({'rst_rcvd': grid_rpt})
            
            if not any([m for m in ['+','-','RR','73'] if m in grid_rpt]): # grid_rpt == grid
                self.qso_info.update({'gridsquare': grid_rpt})

            if message_type == "CQ":
                reply = f"{new_qso_info['call']} {self.myCall} {self.myGrid[:4]}"
                    
            if message_type == "to_me":
                rst_sent = self.qso_info['rst_sent']
                reply = f"{new_qso_info['call']} {self.myCall} {rst_sent}"
                if any([m for m in ['+','-'] if m in grid_rpt]):
                    reply = f"{new_qso_info['call']} {self.myCall} R{rst_sent}"
                if any([m for m in ['R+','R-','RRR'] if m in grid_rpt]):
                    reply = f"{new_qso_info['call']} {self.myCall} RR73"
                if grid_rpt == 'RR73':
                    reply = f"{new_qso_info['call']} {self.myCall} 73"

            self._set_tx_payload(reply)

            if reply.endswith("73"): # do last so any log errors don't prevent sending 73
                if self.adif_logging is not None:
                    gmt = time.gmtime()
                    self.qso_info.update({'time_off': time.strftime("%H%M%S", gmt), 'qso_date_off':time.strftime("%Y%m%d", gmt)})
                    self.adif_logging.log(self.qso_info)
                    self.console_print(f"[PyFT8] Logged QSO with {self.qso_info['call']}")
                self.qso_active = False

    def _set_tx_payload(self, msg_text):
        self.console_print(f"[QSO] Set transmit message to '{msg_text}' (cyc {self.tx_cycle}, {self.tx_freq:5.1f} Hz)")
        if len(msg_text.split(' ')) == 3:           
            symbols = get_ft8_symbols(msg_text)
            audio_bytes = symbols_to_audio_bytes(symbols, f_base = self.tx_freq)
            self.tx_payload = {'audio_bytes':audio_bytes, 'start_gridtime':[0.25, 15.25][self.tx_cycle]}
        else:
            self.console_print(f"[QSO] Message is malformed", color = 'red')
            

    def _transmit_daemon(self):
        while True:
            time_utils.sleep(0.1)
            if self.tx_payload is not None:
                start_gridtime = self.tx_payload['start_gridtime'] 
                grid_time = time_utils.grid_time()
                if start_gridtime <= grid_time < start_gridtime + MAX_TX_START_CYCLETIME:
                    self.rig.ptt_on()
                    self.transmit_audio_data_bytes(self.tx_payload['audio_bytes'])
                    self.rig.ptt_off()
                    self.last_tx_payload = self.tx_payload
                    self.tx_payload = None

    def _find_clear_freq(self, band):
        from numpy.lib.stride_tricks import sliding_window_view
        import numpy as np
        fbin_sum = np.sum(self.wf_data['data'], axis = 0)
        windows = sliding_window_view(fbin_sum, self.wf_data['sig_h'])
        busy_profile = windows.max(axis=1)
        fmax = 950 if band=='60m' else 2000
        f0_idx, fn_idx = int(500/self.wf_data['df']), int(fmax/self.wf_data['df'])
        idx = np.argmin(busy_profile[f0_idx:fn_idx])
        clearest_frequency = (f0_idx + idx) * self.wf_data['df']
        #print(idx, clearest_frequency, np.mean(self.wf_data['data'][:, idx:idx+self.wf_data['sig_h']]))
        return clearest_frequency
