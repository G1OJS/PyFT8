import paho.mqtt.client as mqtt
import threading
import time
from ast import literal_eval
from PyFT8.file_data import File_data

class PSKR_MQTT_listener:

    def __init__(self, file_data, home_square):
        self.home_square = home_square
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = self.on_connect
        mqttc.on_message = self.on_message
        mqttc.connect("mqtt.pskreporter.info", 1883, 60)
        self.file_data = file_data
        threading.Thread(target = mqttc.loop_forever, daemon = True).start()
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        #pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
        print(f"[MQTT] Connected with result code {reason_code}")
        print(f"[MQTT] Requesting mqtt feed for {self.home_square}")
        client.subscribe(f"pskr/filter/v2/+/FT8/+/+/+/{self.home_square}/#")

    def on_message(self, client, userdata, msg):
        try:
            d = literal_eval(msg.payload.decode())
        except:
            return
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for c in [sc, rc]:
            if c[0] not in self.file_data.data:
                self.file_data.data[c[0]]=c[1]
                self.file_data.save()

if __name__ == '__main__':
    pskr = PSKR_MQTT_listener()

    while True:
        time.sleep(5)
        print(pskr.active_calls.data)
    


    
