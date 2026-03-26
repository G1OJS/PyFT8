import paho.mqtt.client as mqtt
import threading
import time
from ast import literal_eval

class PSKR_MQTT_listener:

    def __init__(self, home_square):
        self.home_square = home_square
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = self.on_connect
        mqttc.on_message = self.on_message
        mqttc.connect("mqtt.pskreporter.info", 1883, 60)
        self.cache = {}
        self.home_call_info = {}
        self.home_activity = {}
        threading.Thread(target = mqttc.loop_forever, daemon = True).start()
        threading.Thread(target = self.count_activity, daemon = True).start()
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        #pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
        print(f"[MQTT] Connected with result code {reason_code}")
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
                if not key in self.home_call_info:
                    self.home_call_info[key] = 0
                self.home_call_info[key] +=1

    def count_activity(self):
        while True:
            time.sleep(5)
            for c_info in self.home_call_info:
                c = c_info.split("_")[0]
                self.home_activity[c] = [0,0]
            for c_info in self.home_call_info:
                c, txrx = c_info.split("_")[:2]
                self.home_activity[c][['Tx','Rx'].index(txrx)] +=1
                
if __name__ == '__main__':
    pskr = PSKR_MQTT_listener("IO90")
        

        

    


    
