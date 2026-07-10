MAX_TX_START_CYCLETIME = 3


class QSO_manager:
    def __init__(self, myCall, myGrid, gui, transmitter):
        self.gui = gui
        self.transmitter = transmitter
        self.myCall, self.myGrid = myCall, myGrid
        self.tx_freq = 750
        self.clear()
        self.gui.console.scroll_print(f"[PyFT8] QSO handler started for {myCall}")

    def clear(self):
        self.transmitter.tx_message = None
        self.last_tx = None
        self.tx_cycle = None
        self.tx_start_grid_time = 0
        self.oStation = {'c':None, 'g':None}
        self.times = {'time_on':None, 'time_off':None}
        self.rpts = {'sent': None, 'rcvd': None}

    def set_tx_message(self, message):
        if gui and self.band_info['b'] is None:
            self.gui.console.scroll_print("[PyFT8] Please select a band before transmitting", color = 'red')
            return
        self.transmitter.tx_message = {'text':message, 'start_gridtime':[0.25, 15.25][self.tx_cycle]}
        self.gui.console.scroll_print(f"[QSO] Set transmit message to '{self.message_to_transmit}' (cyc {self.tx_cycle}, {self.tx_freq:5.1f} Hz)")

    def log(self):
        if adif_logging is not None:
            self.times['time_off'] = time.gmtime()
            adif_logging.log(self.times, self.band_info, self.mStation, self.oStation, self.rpts)
            self.gui.console.scroll_print(f"[PyFT8] Logged QSO with {self.oStation['c']}")

    def progress(self):
        call_a, call_b, grid_rpt = clicked_message.msg_tuple
        isReport    = "+" in grid_rpt or "-" in grid_rpt
        isRReport   = isReport and 'R' in grid_rpt
        isRRR       = 'RRR' in grid_rpt
        isRR73      = 'RR73' in grid_rpt
        is73        = '73' in grid_rpt and not isRR73
        isGrid      = not isReport and not is73 and not isRR73 and not isRRR 

        my_station = qso.mStation
        reply = ""
        self.gui.console.scroll_print(f"[QSO] Clicked on message '{' '.join(clicked_message.msg_tuple)}'")

        if call_a == "CQ":
            qso.clear()
            qso.times['time_on'] = time.gmtime()
            qso.oStation = {'c': call_b, 'g': grid_rpt}
            qso.rpts['sent'] = f"{clicked_message.snr:+03d}"
            qso.tx_freq = clearest_frequency
            qso.tx_cycle = 1 - clicked_message.origin['odd_even']
            qso.set_tx_message(f"{qso.oStation['c']} {my_station['c']} {my_station['g'][:4]}")
            return

        if call_a == my_station['c']:
            if qso.times['time_on'] is None:
                qso.times['time_on'] = time.gmtime()
                qso.tx_freq = clearest_frequency
                qso.tx_cycle = 1 - clicked_message.origin['odd_even']
            if qso.rpts['sent'] is None:
                qso.rpts['sent'] = f"{clicked_message.snr:+03d}"
            qso.oStation['c'] = call_b
            
            if isGrid:
                qso.oStation = {'c': call_b, 'g': grid_rpt}
                reply = f"{qso.oStation['c']} {my_station['c']} {clicked_message.snr:+03d}"
            if isReport:
                reply = f"{qso.oStation['c']} {my_station['c']} R{clicked_message.snr:+03d}"
                qso.rpts['rcvd'] = grid_rpt[-3:]
            if isRReport or isRRR:
                reply = f"{qso.oStation['c']} {my_station['c']} RR73"
            if isRR73:
                reply = f"{qso.oStation['c']} {my_station['c']} 73"

            qso.set_tx_message(reply)

            if reply.endswith("73"): # do last so any log errors don't prevent sending 73
                qso.log()



