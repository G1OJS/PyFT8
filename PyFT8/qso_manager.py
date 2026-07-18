import threading
import time
from PyFT8.time_utils import time_utils
from PyFT8.transmitter import get_ft8_symbols, symbols_to_audio_bytes
MAX_TX_START_CYCLETIME = 3

class QSO_manager:
    def __init__(self, message_broker, rig_control, console_print):
        self.transmit_audio_data_bytes = message_broker.soundcard_out.transmit_audio_data_bytes
        self.get_band_info = message_broker.gui.get_band_info
        self.find_clear_freq = message_broker.rx.find_clear_freq
        self.adif_logging = message_broker.adif_logging
        self.in_qso_with = False
        self.tx_payload = None
        self.tx_cycle = 0
        self.console_print = console_print
        self.rig = rig_control
        self.myCall, self.myGrid = message_broker.myCall, message_broker.myGrid
        self.tx_freq = 750
        self.console_print(f"[PyFT8] QSO handler started for {self.myCall}")
        threading.Thread(target = self._transmit_daemon, daemon = True).start()

    def _start_qso(self, their_call, their_snr, tx_cycle):
        gmt = time.gmtime()
        self.logging_info = {'operator':self.myCall, 'station_callsign':self.myCall, 'my_gridsquare':self.myGrid, 'mode':'FT8',
                             'time_on': time.strftime("%H%M%S", gmt), 'qso_date':time.strftime("%Y%m%d", gmt),
                             'band':self.band_info['current_band'], 'freq':self.band_info['fMHz'],
                             'call':their_call, 'rst_sent':their_snr}
        self.tx_cycle = tx_cycle
        maxfreq = 950 if self.band_info['current_band'] == '60m' else 2500
        self.tx_freq = self.find_clear_freq(maxfreq)
        self.in_qso_with = their_call

    def _add_their_report_or_grid(self, grid_rpt):
        if any([m for m in ['+','-'] if m in grid_rpt]): # grid_rpt == rpt
            self.logging_info.update({'rst_rcvd': grid_rpt})
        if not any([m for m in ['+','-','RR','73'] if m in grid_rpt]): # grid_rpt == grid
            self.logging_info.update({'gridsquare': grid_rpt})

    def _determine_reply(self, message_type, their_call, their_snr):
        if message_type == "CQ":
            reply = f"{their_call} {self.myCall} {self.myGrid[:4]}"   
        if message_type == "to_me":
            reply = f"{their_call} {self.myCall} {their_snr}"
            if any([m for m in ['+','-'] if m in grid_rpt]):
                reply = f"{stheir_call} {self.myCall} R{their_snr}"
            if any([m for m in ['R+','R-','RRR'] if m in grid_rpt]):
                reply = f"{their_call} {self.myCall} RR73"
            if grid_rpt == 'RR73':
                reply = f"{their_call} {self.myCall} 73"
        return reply

    def _end_qso(self):
        if self.adif_logging is not None:
            gmt = time.gmtime()
            self.logging_info.update({'time_off': time.strftime("%H%M%S", gmt), 'qso_date_off':time.strftime("%Y%m%d", gmt)})
            self.adif_logging.log(self.logging_info)
            self.console_print(f"[PyFT8] Logged QSO with {self.logging_info['call']}")
        self.in_qso_with = False

    def on_click(self, clickargs):
        btn_action = clickargs['action']
        self.band_info = self.get_band_info()
        if btn_action in ['MESSAGE_CLICK','CQ'] and self.band_info['current_band'] is None:
            self.console_print("Please select a band before transmitting", color = 'red')
            return
        if btn_action == "SET_BAND":
            self.rig.set_freq_Hz(int(1000000*float(clickargs['fMHz'])))
        if btn_action == "CQ":
            self.clear_qso()
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
        if btn_action == "MESSAGE_CLICK":
            message_type = clickargs['message']['message_type']
            if message_type in ['CQ','to_me']:
                message = clickargs['message']
                their_call, grid_rpt, their_snr, their_tx_cycle = message['their_call'], message['grid_rpt'], message['their_snr'], message['their_tx_cycle']
                if their_call != self.in_qso_with:
                    self._start_qso(their_call, their_snr, 1 - their_tx_cycle)
                self._add_their_report_or_grid(grid_rpt)
                reply = self._determine_reply(message_type, their_call, their_snr)
                self._set_tx_payload(reply)
                if reply.endswith("73"):
                    self._end_qso()

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

