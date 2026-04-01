import threading
import time
import os
import json
from PyFT8.adif import parse_adif

class DiskDict:
    def __init__(self, file):
        self.lock = threading.Lock()
        self.file = file
        self.dict = {}
        self.load()
        threading.Thread(target = self._autosave, daemon = True).start()

    def _autosave(self, autosave_period = 15):
        while True:
            time.sleep(autosave_period)
            self.save()

    def load(self):
        with self.lock:        
            if(os.path.exists(self.file)):
                with open(f"{self.file}","r") as f:
                    self.dict = json.load(f)

    def save(self):
        with self.lock:
            tmp_file = f"{self.file}.tmp"
            with open(tmp_file, "w") as f:
                json.dump(self.dict, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.file)

class CallData:
    def __init__(self, config_folder, my_call, home_square, pskr_refresh_mins):
        self.pskr_refresh_mins = pskr_refresh_mins
        self.my_call, self.home_square = my_call, home_square
        self.callsign_cache = DiskDict(f"{config_folder}/callsign_cache.json")
        self.spots = DiskDict(f"{config_folder}/spots.json")
        self.worked_before_cache = {}
        self.home_activity = {}
        self.home_most_remotes = {}
        self.lock = threading.Lock()
        self.process_existing_log(f"{config_folder}/PyFT8.adi")
        #threading.Thread(target = self.count_activity, daemon = True).start()

    def process_existing_log(self, logfile):
        import datetime
        with open(logfile, 'r') as f:
            for l in f.readlines():
                if parse_adif(l, 'mode') == "FT8":
                    c, b, d, t = parse_adif(l, 'call'), parse_adif(l, 'band'), parse_adif(l, 'qso_date'), parse_adif(l, 'time_on')
                    tm = time.mktime(datetime.datetime.strptime(d+t, "%Y%m%d%H%M%S").timetuple())
                    self.worked_before_cache[c] = tm
                    self.worked_before_cache[c + "_"+b+"_FT8"] = tm

    def store_best_location(self, call_loc):
        existing_loc = self.callsign_cache.dict.get(call_loc[0], '')
        if len(call_loc[1]) > len(existing_loc):
            self.callsign_cache.dict[call_loc[0]] = call_loc[1]

    def add_spots_info(self, band, se, re, t, rp):
        for i, home_entity in enumerate([se, re]):
            if self.home_square in home_entity[1]:
                home_role = ['Tx','Rx'][i]
                home_entity = [se, re][i]
                other_entity = [se, re][1-i]
                key = f"{band}_{home_entity[0]}_{home_role}"
                self.spots.dict.setdefault(key, {})
                self.spots.dict[key][other_entity[0]] = {'t': int(t), 'rp':int(rp)}

    def save_mqtt_spot(self, spot_dict):
        d = spot_dict
        se, re = (d['sc'], d['sl']), (d['rc'], d['rl'])
        self.store_best_location(se)
        self.add_spots_info(d['b'], se, re, time.time(), d['rp'])
                
    def count_activity(self):
        import numpy as np
        while True:
            time.sleep(5)
            self.home_activity = {}
            self.home_most_remotes = {}
            with self.lock:
                # clear counters for each band
                for b in self.home_activity:
                    self.home_activity[b] = [0, 0]
                for b in self.home_most_remotes:
                    self.home_most_remotes[b] = [('',0), ('',0)]

                # keep only the remote spots that happened in the self.pskr_refresh_mins window
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    band_TxRx_homecall_report_times = [t for t in band_TxRx_homecall_report_times if (time.time() - t) < 60*self.pskr_refresh_mins]
                    self.band_TxRx_homecall_report_times.data[band_TxRx_homecall] = band_TxRx_homecall_report_times

                # count number of local Tx and Rx, and identify the local Tx and Rx with most remote spots
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    if len(band_TxRx_homecall_report_times):
                        b, iTxRx, c = band_TxRx_homecall
                        self.home_activity.setdefault(b, [0, 0])
                        self.home_activity[b][iTxRx] +=1
                        self.home_most_remotes.setdefault(b, [('',0), ('',0)])
                        nremotes = len(band_TxRx_homecall_report_times)
                        if nremotes>self.home_most_remotes[b][iTxRx][1]:
                            self.home_most_remotes[b][iTxRx] = (c, nremotes)

    def get_spot_counts(self, band, call):
        tx_reports = self.band_TxRx_homecall_report_times.data.get((band, 0, call), [])
        rx_reports = self.band_TxRx_homecall_report_times.data.get((band, 1, call), [])
        n_spotting = len(tx_reports) if tx_reports else 0
        n_spotted = len(rx_reports) if rx_reports else 0
        return n_spotted, n_spotting            
                

