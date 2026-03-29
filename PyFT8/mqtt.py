import paho.mqtt.client as mqtt
import threading
import time
from ast import literal_eval

class PSKR_MQTT_listener:

    def __init__(self, my_call, home_square):
        self.my_call = my_call
        self.hearing_me = {}
        self.home_square = home_square
        self.cache = {}
        self.band_TxRx_homecall_report_times = {}
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
            if call not in self.cache:
                self.cache[call] = loc
            if self.home_square in loc:
                key = f"{d['b']}_{['Tx','Rx'][i]}_{call}"
                if not key in self.band_TxRx_homecall_report_times:
                    with self.lock:
                        self.band_TxRx_homecall_report_times[key] = []
                self.band_TxRx_homecall_report_times[key].append(time.time())
            if True or d['sc'] == self.my_call:
                if d['b'] not in self.hearing_me:
                    self.hearing_me[d['b']] = {}
                if d['rc'] not in self.hearing_me[d['b']]:
                    self.hearing_me[d['b']][d['rc']] = time.time()
            
    def count_activity(self):
        while True:
            time.sleep(5)
            self.band_TxRx_homecall_countremotes = {}
            with self.lock:
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times:
                    b = band_TxRx_homecall.split("_")[0]
                    self.home_activity[b] = [0,0]
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times:
                    b, tr, c = band_TxRx_homecall.split("_")
                    report_times = self.band_TxRx_homecall_report_times[band_TxRx_homecall]
                    report_times = [t for t in report_times if (time.time() - t) < 15*60]
                    self.band_TxRx_homecall_report_times[band_TxRx_homecall] = report_times
                    nremotes = len(report_times)
                    self.home_activity[b][['Tx','Rx'].index(tr)] +=1
                    if not b in self.home_most_remotes:
                        self.home_most_remotes[b] = [('',0), ('',0)]
                    if nremotes>self.home_most_remotes[b][['Tx','Rx'].index(tr)][1]:
                        self.home_most_remotes[b][['Tx','Rx'].index(tr)] = (c, nremotes)
                for b in self.hearing_me:
                    newdict = {}
                    for c in self.hearing_me[b]:
                        if (time.time() - self.hearing_me[b][c]) < 15*60:
                            newdict[c] = self.hearing_me[b][c]
                    self.hearing_me[b] = newdict

    def get_spot_counts(self, band, call):
        n_spotting = len(self.band_TxRx_homecall_report_times.get(f"{band}_Tx_{call}", []))
        n_spotted = len(self.band_TxRx_homecall_report_times.get(f"{band}_Rx_{call}", []))
        return n_spotted, n_spotting
                
if __name__ == '__main__':
    pskr = PSKR_MQTT_listener("IO90")
        

        

    


    
