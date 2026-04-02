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
        threading.Thread(target = self._manage, daemon = True).start()

    def _manage(self, autosave_period = 15):
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
            snapshot = dict(self.dict)
        tmp_file = f"{self.file}.tmp"
        with open(tmp_file, "w") as f:
            json.dump(snapshot, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, self.file)

class CallData:
    def __init__(self, config_folder, my_call, home_square, pskr_refresh_mins):
        self.pskr_refresh_mins = pskr_refresh_mins
        self.my_call, self.home_square = my_call, home_square[:4]
        self.callsign_cache = DiskDict(f"{config_folder}/callsign_cache.json")
        self.spots = DiskDict(f"{config_folder}/spots.json")
        self.worked_before_cache = {}
        self.new_entries = []
        self.process_existing_log(f"{config_folder}/PyFT8.adi")
        threading.Thread(target = self._prune_spots_info, daemon = True).start()

    def process_existing_log(self, logfile):
        import calendar
        with open(logfile, 'r') as f:
            for l in f.readlines():
                if parse_adif(l, 'mode') == "FT8":
                    c, b, d, t = parse_adif(l, 'call'), parse_adif(l, 'band'), parse_adif(l, 'qso_date'), parse_adif(l, 'time_on')
                    time_tuple = time.strptime(d+t, "%Y%m%d%H%M%S")
                    tm = calendar.timegm(time_tuple)
                    self.worked_before_cache[c] = tm
                    self.worked_before_cache[c + "_"+b+"_FT8"] = tm

    def get_best_location(self, call):
        return self.callsign_cache.dict.get(call, '')

    def store_best_location(self, call_loc):
        existing_loc = self.callsign_cache.dict.get(call_loc[0], '')
        if len(call_loc[1]) > len(existing_loc):
            self.callsign_cache.dict[call_loc[0]] = call_loc[1]

    def add_spots_info(self, band, se, re, t, rp):
        self.store_best_location(se)
        for i, home_entity in enumerate([se, re]):
            if self.home_square in home_entity[1]:
                home_role = ['Tx','Rx'][i]
                home_entity = [se, re][i]
                other_entity = [se, re][1-i]
                key = [home_role, band, home_entity[0], other_entity[0]]
                if self.my_call in key:
                    if '|'.join(key) not in self.spots.dict:
                        self.new_entries.append('|'.join(key))
                self.spots.dict['|'.join(key)] = [int(t), int(rp)]

    def save_mqtt_spot(self, spot_dict):
        d = spot_dict
        se, re = (d['sc'], d['sl']), (d['rc'], d['rl'])
        self.add_spots_info(d['b'], se, re, time.time(), d['rp'])

    def _prune_spots_info(self, period = 15):
        while True:
            time.sleep(period)
            t_cut = time.time() - 60*self.pskr_refresh_mins
            with self.spots.lock:
                data = dict(self.spots.dict)
                keys = [k for k in data if data[k][0] > t_cut or self.my_call in k]
                self.spots.dict = {k:data[k] for k in keys}

