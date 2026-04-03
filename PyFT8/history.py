from PyFT8.pskreporter import PSKR_MQTT_listener
import threading, time, os, pickle

class DiskDict:
    def __init__(self, file):
        self.lock = threading.Lock()
        self.file = file
        self.data = {}
        self.load()
        threading.Thread(target = self._autosave, daemon = True).start()

    def _autosave(self, autosave_period = 15):
        while True:
            time.sleep(autosave_period)
            self.save()

    def load(self):
        with self.lock:        
            if(os.path.exists(self.file)):
                with open(f"{self.file}","rb") as f:
                    self.data = pickle.load(f)

    def save(self):
        with self.lock:
            tmp_file = f"{self.file}.tmp"
            with open(tmp_file, "wb") as f:
                pickle.dump(self.data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.file)

class History:
    def __init__(self, config_folder, my_call, home_square, pskr_refresh_mins):
        self.pskr_refresh_mins = pskr_refresh_mins
        self.my_call = my_call
        self.home_square = home_square
        self.hearing_me = DiskDict(f"{config_folder}/hearing_me.pkl")   # all-time record of hearing me
        self.heard_by_me = DiskDict(f"{config_folder}/heard_by_me.pkl") # all-time record of heard by me
        self.hearing_me_new = []
        self.heard_by_me_new = []
        self.callsign_cache = DiskDict(f"{config_folder}/callsign_cache.pkl") # all time cache call -> fine locator
        self.band_TxRx_homecall_report_times = DiskDict(f"{config_folder}/report_times.pkl") # last 20 mins data -> per band tx/rx & current band detail
        self.home_activity = {}
        self.home_most_remotes = {}
        self.lock = threading.Lock()
        mqtt = PSKR_MQTT_listener(home_square, self.add_mqtt_spot)
        threading.Thread(target = self.count_activity, daemon = True).start()

    def add_mqtt_spot(self, d):
        tnow = int(time.time())
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for iTxRx, call_loc in enumerate([sc, rc]):
            call, loc = call_loc
            self.store_best_location(call, loc)
            if self.home_square in loc:
                self.add_homespots_record((d['b'], iTxRx, call), tnow)
        if d['sc'] == self.my_call:
            if d['rc'] not in self.hearing_me.data[d['b']]:
                self.hearing_me_new.append(d['rc'])
            self.add_myspots_record(self.hearing_me.data, d['b'], d['rc'], tnow, d['rp'])
        if d['rc'] == self.my_call:
            if d['sc'] not in self.heard_by_me.data[d['b']]:
                self.heard_by_me_new.append(d['sc'])
            self.add_myspots_record(self.heard_by_me.data, d['b'], d['sc'], tnow, d['rp'])

    def store_best_location(self, call, loc):
        existing_loc = self.callsign_cache.data.get(call, '')
        if len(loc) > len(existing_loc):
            self.callsign_cache.data[call] = loc
        
    def add_homespots_record(self, key, t):
        self.band_TxRx_homecall_report_times.data.setdefault(key, [])
        self.band_TxRx_homecall_report_times.data[key].append(int(t))

    def add_myspots_record(self, data, band, call, t, rp):
        data.setdefault(band, {})
        data[band][call] = {'t': int(t),'rp':int(rp)}
                 
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
                        current_winner = self.home_most_remotes[b][iTxRx]
                        if nremotes > current_winner[1]:
                            if c != self.my_call:
                                self.home_most_remotes[b][iTxRx] = (c, nremotes)

    def get_spot_counts(self, band, call):
        tx_reports = self.band_TxRx_homecall_report_times.data.get((band, 0, call), [])
        rx_reports = self.band_TxRx_homecall_report_times.data.get((band, 1, call), [])
        n_spotting = len(tx_reports) if tx_reports else 0
        n_spotted = len(rx_reports) if rx_reports else 0
        return n_spotted, n_spotting
                
