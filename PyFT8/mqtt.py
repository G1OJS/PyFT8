import paho.mqtt.client as mqtt
import threading
import time
from ast import literal_eval

SPOTLIFE = 15*60

import os
import pickle

class DiskDict:
    def __init__(self, file):
        self.file = file
        self.data = {}
        self.load()
        threading.Thread(target = self._autosave, daemon = True).start()

    def _autosave(self, autosave_period = 15):
        while True:
            time.sleep(autosave_period)
            self.save()

    def load(self):
        if(os.path.exists(self.file)):
            with open(f"{self.file}","rb") as f:
                self.data = pickle.load(f)

    def save(self):
        if self.data:
            with open(f"{self.file}","wb") as f:
                pickle.dump(self.data, f)

class PSKR_MQTT_listener:
    def __init__(self, config_folder, my_call, home_square):
        self.my_call = my_call
        self.hearing_me = DiskDict(f"{config_folder}/hearing_me.pkl")
        self.home_square = home_square
        self.callsign_cache = DiskDict(f"{config_folder}/callsign_cache.pkl")
        self.band_TxRx_homecall_report_times = DiskDict(f"{config_folder}/report_times.pkl")
        self.band_TxRx_homecall_countremotes = {}
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
        #pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
        print(f"[MQTT] Requesting mqtt feed for {self.home_square}")
        client.subscribe(f"pskr/filter/v2/+/FT8/+/+/{self.home_square}/#")
        client.subscribe(f"pskr/filter/v2/+/FT8/+/+/+/{self.home_square}/#")


    def on_message(self, client, userdata, msg):
        try:
            d = literal_eval(msg.payload.decode())
        except:
            return
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for i, c in enumerate([sc, rc]):
            call, loc = c
            if call not in self.callsign_cache.data:
                self.callsign_cache.data[call] = loc
            if self.home_square in loc:
                key = f"{d['b']}_{['Tx','Rx'][i]}_{call}"
                if not key in self.band_TxRx_homecall_report_times.data:
                    with self.lock:
                        self.band_TxRx_homecall_report_times.data[key] = []
                self.band_TxRx_homecall_report_times.data[key].append(time.time())
            if d['sc'] == self.my_call:
                if d['b'] not in self.hearing_me.data:
                    self.hearing_me.data[d['b']] = {}
                if d['rc'] not in self.hearing_me.data[d['b']]:
                    self.hearing_me.data[d['b']][d['rc']] = {'t':time.time(), 'rp':d['rp'], 'c':d['rc']}

    def count_activity(self):
        import numpy as np
        while True:
            time.sleep(5)
            self.home_activity = {}
            self.band_TxRx_homecall_countremotes = {}
            self.home_most_remotes = {}
            with self.lock:
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    b = band_TxRx_homecall.split("_")[0]
                    self.home_activity[b] = [0, 0]

                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    band_TxRx_homecall_report_times = [t for t in band_TxRx_homecall_report_times if (time.time() - t) < SPOTLIFE]
                    self.band_TxRx_homecall_report_times.data[band_TxRx_homecall] = band_TxRx_homecall_report_times

                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    if len(band_TxRx_homecall_report_times):
                        b, tr, c = band_TxRx_homecall.split("_")
                        self.home_activity[b][['Tx','Rx'].index(tr)] +=1
                        nremotes = len(band_TxRx_homecall_report_times)
                        if not b in self.home_most_remotes:
                            self.home_most_remotes[b] = [('',0), ('',0)]
                        if nremotes>self.home_most_remotes[b][['Tx','Rx'].index(tr)][1]:
                            self.home_most_remotes[b][['Tx','Rx'].index(tr)] = (c, nremotes)

                for b in self.hearing_me.data:
                    newdict = {}
                    for c in self.hearing_me.data[b]:
                        if (time.time() - self.hearing_me.data[b][c]['t']) < SPOTLIFE:
                            newdict[c] = self.hearing_me.data[b][c]
                    self.hearing_me.data[b] = newdict

    def get_spot_counts(self, band, call):
        tx_reports = self.band_TxRx_homecall_report_times.data.get(f"{band}_Tx_{call}", [])
        rx_reports = self.band_TxRx_homecall_report_times.data.get(f"{band}_Rx_{call}", [])
        n_spotting = len(tx_reports) if tx_reports else 0
        n_spotted = len(rx_reports) if rx_reports else 0
        return n_spotted, n_spotting
                
if __name__ == '__main__':
    pskr = PSKR_MQTT_listener("IO90")
        

        

    


    
