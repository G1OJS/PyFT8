import paho.mqtt.client as mqtt
import threading
import time
from ast import literal_eval

SPOTLIFE = 15*60

import os
import pickle

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
                
class PSKR_MQTT_listener:
    def __init__(self, config_folder, my_call, home_square):
        self.my_call = my_call
        self.hearing_me = DiskDict(f"{config_folder}/hearing_me.pkl")
        self.heard_by_me = DiskDict(f"{config_folder}/heard_by_me.pkl")
        self.home_square = home_square
        self.callsign_cache = DiskDict(f"{config_folder}/callsign_cache.pkl")
        self.band_TxRx_homecall_report_times = DiskDict(f"{config_folder}/report_times.pkl")
        self.band_TxRx_homecall_couniTxRxemotes = {}
        self.home_activity = {}
        self.home_most_remotes = {}
        self.lock = threading.Lock()
        
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = self.on_connect
        mqttc.on_message = self.on_message
        try:
            mqttc.connect("mqtt.pskreporter.info", 1883, 60)
        except:
            print("[MQTT] connection error")
        threading.Thread(target = mqttc.loop_forever, daemon = True).start()
        threading.Thread(target = self.count_activity, daemon = True).start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        #pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercouniTxRxy}/{receivercouniTxRxy}
        print(f"[MQTT] Requesting mqtt feed for {self.home_square}")
        client.subscribe(f"pskr/filter/v2/+/FT8/+/+/{self.home_square}/#")
        client.subscribe(f"pskr/filter/v2/+/FT8/+/+/+/{self.home_square}/#")

    def on_message(self, client, userdata, msg):
        try:
            d = literal_eval(msg.payload.decode())
        except:
            return
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for iTxRx, c in enumerate([sc, rc]):
            call, loc = c
            self.callsign_cache.data[call] = loc
            if self.home_square in loc:
                key = (d['b'], iTxRx, call)
                self.band_TxRx_homecall_report_times.data.setdefault(key, [])
                self.band_TxRx_homecall_report_times.data[key].append(time.time())
            if d['sc'] == self.my_call:
                self.hearing_me.data.setdefault(d['b'], {})
                new = (d['rc'] not in self.hearing_me.data)
                new_on_band = (d['rc'] not in self.hearing_me.data[d['b']])
                self.hearing_me.data[d['b']][d['rc']] = {'t': time.time(),'rp': d['rp'],'c': d['rc'], 'new':''}
                if new_on_band:
                    self.hearing_me.data[d['b']][d['rc']].update({'new':'new_on_band'})
                if new:
                    self.hearing_me.data[d['b']][d['rc']].update({'new':'new'})
            if d['rc'] == self.my_call:
                self.heard_by_me.data.setdefault(d['b'], {})
                new = (d['sc'] not in self.heard_by_me.data)
                new_on_band = (d['sc'] not in self.heard_by_me.data[d['b']])
                self.heard_by_me.data[d['b']][d['sc']] = {'t': time.time(),'rp': d['rp'],'c': d['sc'], 'new':''}
                if new_on_band:
                    self.heard_by_me.data[d['b']][d['sc']].update({'new':'new_on_band'})
                if new:
                    self.heard_by_me.data[d['b']][d['sc']].update({'new':'new'})
                               
    def count_activity(self):
        import numpy as np
        while True:
            time.sleep(5)
            self.home_activity = {}
            self.band_TxRx_homecall_couniTxRxemotes = {}
            self.home_most_remotes = {}
            with self.lock:
                # clear counters for each band
                for b in self.home_activity:
                    self.home_activity[b] = [0, 0]
                for b in self.home_most_remotes:
                    self.home_most_remotes[b] = [('',0), ('',0)]

                # keep only the remote spots that happened in the SPOTLIFE window
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    band_TxRx_homecall_report_times = [t for t in band_TxRx_homecall_report_times if (time.time() - t) < SPOTLIFE]
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
                
if __name__ == '__main__':
    pskr = PSKR_MQTT_listener("IO90")
        

        

    


    
