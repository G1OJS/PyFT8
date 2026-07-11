import threading
from PyFT8.time_utils import time_utils
from PyFT8.transmitter import get_ft8_symbols, symbols_to_audio_bytes
MAX_TX_START_CYCLETIME = 3


class QSO_manager:
    def __init__(self, myCall, myGrid, console_print, send_bytes, rig, wf_data, adif_logging):
        self.send_bytes = send_bytes
        self.adif_logging = adif_logging
        self.tx_payload = None
        self.wf_data = wf_data
        self.console_print = console_print
        self.rig = rig
        self.band_info = {'current_band': None, 'fMHz':0, 'time_set':0}
        self.myCall, self.myGrid = myCall, myGrid
        self.theirCall, self.theirGrid = None, None
        self.tx_freq = 750
        self.reset()
        self.console_print(f"[PyFT8] QSO handler started for {self.myCall}")
        threading.Thread(target = self.td, daemon = True).start()

    def get_band_info(self):
        return self.band_info

    def band_is_set(self):
        if self.band_info['current_band'] is None:
            self.console_print("Please select a band before transmitting", color = 'red')
            return False
        return True

    def reset(self):
        self.tx_payload = None
        self.last_tx_payload = None
        self.tx_cycle = None
        self.tx_start_grid_time = 0
        self.times = {'time_on':None, 'time_off':None}
        self.rpts = {'sent': None, 'rcvd': None}
        self.tx_freq = self.find_clear_freq(self.band_info['current_band'])

    def prep_and_arm_transmit(self, message):
        symbols = get_ft8_symbols(message)
        audio_bytes = symbols_to_audio_bytes(symbols, f_base = self.tx_freq)
        self.tx_payload = {'audio_bytes':audio_bytes, 'start_gridtime':[0.25, 15.25][self.tx_cycle]}
        self.console_print(f"[QSO] Set transmit message to '{message}' (cyc {self.tx_cycle}, {self.tx_freq:5.1f} Hz)")

    def td(self):
        while True:
            time_utils.sleep(0.1)
            if self.tx_payload is not None:
                start_gridtime = self.tx_payload['start_gridtime'] 
                grid_time = time_utils.grid_time()
                if start_gridtime <= grid_time < start_gridtime + MAX_TX_START_CYCLETIME:
                    self.rig.ptt_on()
                    self.send_bytes(self.tx_payload['audio_bytes'])
                    self.rig.ptt_off()
                    self.last_tx_payload = self.tx_payload
                    self.tx_payload = None

    def progress(self, clicked_msg_tuple, odd_even, snr):
        call_a, call_b, grid_rpt = clicked_msg_tuple
        self.theirCall = call_b
        isReport    = "+" in grid_rpt or "-" in grid_rpt
        isRReport   = isReport and 'R' in grid_rpt
        isRRR       = 'RRR' in grid_rpt
        isRR73      = 'RR73' in grid_rpt
        is73        = '73' in grid_rpt and not isRR73
        isGrid      = not isReport and not is73 and not isRR73 and not isRRR
        
        reply = ""
        self.console_print(f"[QSO] Clicked on message '{' '.join(clicked_msg_tuple)}'")

        if call_a == "CQ":
            self.reset()
            self.times['time_on'] = time_utils.gmtime()
            self.theirGrid =  grid_rpt
            self.rpts['sent'] = f"{snr:+03d}"
            self.tx_cycle = 1 - odd_even
            self.prep_and_arm_transmit(f"{self.theirCall} {self.myCall} {self.myGrid[:4]}")
            return

        if call_a == self.myCall:
            if self.times['time_on'] is None:
                self.times['time_on'] = time_utils.gmtime()
                self.tx_cycle = 1 - odd_even
            if self.rpts['sent'] is None:
                self.rpts['sent'] = f"{snr:+03d}"
            self.theirCall = call_b
            
            if isGrid:
                self.theirGrid =  grid_rpt
                reply = f"{self.theirCall} {self.myCall} {snr:+03d}"
            if isReport:
                reply = f"{self.theirCall} {self.myCall} R{snr:+03d}"
                self.rpts['rcvd'] = grid_rpt[-3:]
            if isRReport or isRRR:
                reply = f"{self.theirCall} {self.myCall} RR73"
            if isRR73:
                reply = f"{self.theirCall} {self.myCall} 73"

            self.prep_and_arm_transmit(reply)

            if reply.endswith("73"): # do last so any log errors don't prevent sending 73
                if self.adif_logging is not None:
                    self.times['time_off'] = time_utils.gmtime()
                    self.adif_logging.log(self.times, self.band_info, {'c':self.myCall,'g':self.myGrid}, {'c':self.theirCall,'g':self.theirGrid}, self.rpts)
                    self.console_print(f"[PyFT8] Logged QSO with {self.theirCall}")

    def on_click(self, btn_def):
        btn_action = btn_def['action']
        if btn_action == "MESSAGE_CLICK":
            if self.band_is_set(): 
                self.progress(btn_def['msg_tuple'], btn_def['odd_even'], btn_def['snr'])
        if btn_action == "CQ":
            if self.band_is_set():                
                self.reset()
                self.tx_cycle = time_utils.odd_even()
                if time_utils.cycle_time() > MAX_TX_START_CYCLETIME:
                   self.tx_cycle = 1-self.tx_cycle 
                self.prep_and_arm_transmit(f"CQ {self.myCall} {self.myGrid[:4]}")
        if btn_action == "RPT_LAST":
            self.tx_payload = self.last_tx_payload
        if btn_action == "TX_OFF":
            self.console_print("[PyFT8] Set PTT Off")
            self.rig.ptt_off()
            self.tx_cycle = None
        if(btn_action == 'SET_BAND'):
            current_band, freqMHz = btn_def['band'], btn_def['freq']
            self.band_info = {'current_band':current_band, 'fMHz':freqMHz, 'time_set':time_utils.time()}
            self.rig.set_freq_Hz(int(1000000*float(self.band_info['fMHz'])))
            self.console_print(f"[PyFT8] Set band: {self.band_info['current_band']} {self.band_info['fMHz']}")

    def find_clear_freq(self, band):
        from numpy.lib.stride_tricks import sliding_window_view
        import numpy as np
        fbin_sum = np.sum(self.wf_data['data'], axis = 0)
        windows = sliding_window_view(fbin_sum, self.wf_data['sig_h'])
        busy_profile = windows.max(axis=1) 
        fmax = 950 if band=='60m' else 2000
        f0_idx, fn_idx = int(500/self.wf_data['df']), int(fmax/self.wf_data['df'])
        idx = np.argmin(busy_profile[f0_idx:fn_idx])
        clearest_frequency = (f0_idx + idx) * self.wf_data['df']
        return clearest_frequency
