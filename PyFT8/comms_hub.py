import queue, threading
from PyFT8.time_utils import time_utils

class Broker():
    def __init__(self, testing):
        self.myCall, self.myGrid = None, None
        self.rx = None
        self.history = None
        self.gui = None
        self.qso_manager = None
        self.history = None
        self.pskr_upload = None
        self.message_queue = queue.Queue()
        self.message_queue_non_time_critical = queue.Queue()
        self.waterfall_data = None
        self.configured_bands = None
        self.on_decode = None
        self.hearing_me_since_mins = None
        threading.Thread(target = self._process_message_ntc, args = (testing,), daemon = True).start()

    def register_on_decode(self, func): # used by testing code
        self.on_decode = func

    def register_qso_manager(self, qsm):
        self.qso_manager = qsm
        
    def process_message(self, message):
        hail, their_call, grid_rpt = message['hail'], message['their_call'], message['grid_rpt']
        cyclestart_string, their_snr = message['cyclestart_string'], message['their_snr']
        mtype_val = 0 + 1*(their_call == self.myCall) + 2*(hail == self.myCall) + 3*(their_call != self.myCall and hail.startswith('CQ'))
        mtype = ['generic', 'from_me', 'to_me', 'CQ'][mtype_val]        
        message.update( {'message_type':mtype, 'display_text':f"{hail} {their_call} {grid_rpt}",
                              'priority':(mtype == 'to_me' or mtype == 'CQ')} )
        if message['priority']:
            if self.gui:
                self.gui.display_message(message)

        if self.qso_manager.in_qso_with == their_call:
            if hail == self.myCall:
                self.qso_manager.auto_reply_to_message(message)

        if self.on_decode:
            self.on_decode(message)
        m = message
        screen_format = f"{cyclestart_string} {their_snr} {m['dt']:4.1f} {m['fHz']:4.0f} ~ {hail} {their_call} {grid_rpt}"
        print(f"{screen_format:50s} decoded@ {m['decode_completed'] %15:5.1f}s, dec = {m['decode_status']}")
        self.message_queue_non_time_critical.put(message)

    def _process_message_ntc(self, testing):
        while True:
            time_utils.sleep(0.25)
            while not self.message_queue_non_time_critical.empty():
                time_utils.sleep(0.01)
                m = self.message_queue_non_time_critical.get()
                band_info = None
                if self.gui:
                    band_info = self.gui.get_band_info()
                    if not m['priority']:
                        self.gui.display_message(m)
                    else:
                        if self.history:
                            current_band, their_call = self.gui.get_band_info()['current_band'], m['their_call']
                            hearing_me = ''
                            if self.hearing_me_since_mins is not None:
                                if self.history.is_hearing_me(current_band, their_call, self.hearing_me_since_mins):
                                    hearing_me = '@'
                            wb_text = self.history.get_worked_before_info(current_band, their_call)
                            geo_text = self.history.get_geo_text(their_call)
                            new_display_text = f"{m['display_text']} {hearing_me} {wb_text} {geo_text}"
                            self.gui.update_message( m['display_text'], {'hearing_me':hearing_me, 'wb_text':wb_text,
                                                        'geo_text':geo_text, 'display_text':new_display_text } )
                if band_info and not testing:
                    if m['their_call'] != 'not':
                        if self.history:
                            self.history.process_message_for_history(m, band_info, self.myCall)
                        if self.pskr_upload:
                            if float(band_info['time_set']) < time_utils.time() - 10: # bad QRG Guard
                                if m['their_call'] != self.myCall:
                                    self.pskr_upload.add_report(m['their_call'], int(1000000*float(band_info['fMHz'])) + m['fHz'],
                                                           m['their_snr'], 'FT8', 1, int(time_utils.time()))



