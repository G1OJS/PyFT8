import queue, threading
from PyFT8.time_utils import time_utils

class Broker():
    def __init__(self):
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
        threading.Thread(target = self._process_message_ntc, daemon = True).start()

    def process_message(self, message_dict):
        hail, their_call, grid_rpt = message_dict['hail'], message_dict['their_call'], message_dict['grid_rpt']

        #screen_format = ' '.join(screen_info)
        #print(f"{screen_format:50s} decoded@ {decode_info['decode_completed']}s, dec = {decode_info['decode_status']}")

        mtype_val = 0 + 1*(their_call == self.myCall) + 2*(hail == self.myCall) + 3*(their_call != self.myCall and hail.startswith('CQ'))
        mtype = ['generic', 'from_me', 'to_me', 'CQ'][mtype_val]        
        message_dict.update( {'message_type':mtype, 'display_text':f"{hail} {their_call} {grid_rpt}",
                              'priority':(mtype == 'to_me' or mtype == 'CQ')} )
        
        if self.history:
            current_band = self.gui.get_band_info()['current_band'] 
            hearing_me, wb_text, geo_text = self.history.get_message_extra_info(their_call, current_band)
            display_text = f"{message_dict['hail']} {message_dict['their_call']} {message_dict['grid_rpt']} {hearing_me} {wb_text} {geo_text}"
            message_dict.update( {'hearing_me':hearing_me, 'wb_text':wb_text, 'geo_text':geo_text, 'display_text':display_text } )            
        if message_dict['priority']:
            self.gui.display_message(message_dict)

        self.message_queue_non_time_critical.put(message_dict)

    def _process_message_ntc(self):
        while True:
            time_utils.sleep(0.25)
            while not self.message_queue_non_time_critical.empty():
                band_info = self.gui.get_band_info()
                time_utils.sleep(0.01)
                m = self.message_queue_non_time_critical.get()
                if not m['priority']:
                    self.gui.display_message(m)                   
                if m['their_call'] != 'not':
                    if self.history:
                        self.history.process_message(m, band_info, self.myCall)
                    if self.pskr_upload:
                        if band_info['fMHz']:
                            if m['their_call'] != myCall:
                                self.pskr_upload.add_report(m['their_call'], int(1000000*float(band_info['fMHz'])) + m['fHz'],
                                                       m['their_snr'], 'FT8', 1, int(time_utils.time()))



