import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import serial
from PyFT8.comms_hub import config
import PyFT8.timers as timers
import threading
from PyFT8.comms_hub import config, start_UI, send_to_ui_ws

class AntennaControl:
    
    def __init__(self):
        timers.timedLog(f"[Antennas] Connecting to {config.AC_port}")
        self.arduino = False
        self.running = True
        try:
            self.arduino = serial.Serial(config.AC_port, baudrate=config.AC_baudrate, timeout=0.1)
        except:
            pass
        if (self.arduino):
            timers.timedLog(f"[Antennas] Connected to {config.AC_port}")
            threading.Thread(target = self.monitor_arduino, daemon=True).start()

            
    def send_command(self, c):
        if c:
            if("<T" in c):
                timers.timedLog(f"[Antennas] Send 'TUNING' message to UI")
                send_to_ui_ws("antenna_control", {'MagloopTuning':'TUNING'})
            timers.timedLog(f"[Antennas] Send command {c}")
            self.arduino.write(c.encode('UTF-8'))

    def monitor_arduino(self):
        while self.running:
            while self.arduino.in_waiting == 0:
                timers.sleep(0.25)
            d = self.arduino.readline()
            if(b"TUNED" in d):
                timers.timedLog(f"[Antennas] Send 'TUNED' message to UI")
                send_to_ui_ws("antenna_control", {'MagloopTuning':'TUNED'})
