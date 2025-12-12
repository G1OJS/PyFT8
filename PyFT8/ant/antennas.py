
import serial
from PyFT8.comms_hub import config
import PyFT8.timers as timers

class AntennaControl:
    
    def __init__(self):
        timers.timedLog(f"[Antennas] Connecting to {config.AC_port}")
        self.arduino = False
        try:
            self.arduino = serial.Serial(config.AC_port, baudrate=config.AC_baudrate, timeout=0.1)
        except:
            pass
        if (self.arduino):
            timers.timedLog(f"[Antennas] Connected to {config.AC_port}")
            
    def send_command(self, c):
        if c:
            s = f"<{c}>"
            timers.timedLog(f"[Antennas] Send command {s}")
            self.arduino.write(s.encode('UTF-8'))

