
import PyFT8.timers as timers

class IcomCIV:
    import serial

    def __init__(self, port='COM4', baudrate=9600, timeout=0.1):
        self.serial_port = False
        try:
            self.serial_port = self.serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
            if (self.serial_port):
                timers.timedLog(f"Connected to {port}")
        except IOError:
            print(f"Couldn't connect to {port} - running without CI-V")    
        
    def sendCAT(self, cmd):
        msg = b"".join([b'\xfe\xfe\x88\xe0', cmd, b'\xfd'])
        timers.timedLog(f"CAT: {msg}")
        if(not self.serial_port): return
        self.serial_port.write(msg)

    def getFreqHz(self):
        while self.serial_port.read():
            pass
        timers.timedLog(f"CAT command: get frequency")
        self.sendCAT(b'\x03')
        if(not self.serial_port): return
        resp = self.serial_port.read_until()
        timers.timedLog(f"CAT: Icom responded with {resp}")
        if(len(resp)<10):
            return False
        return int("".join(f"{(b >> 4) & 0x0F}{b & 0x0F}" for b in reversed(resp[11:16])))

    def setFreqHz(self, freqHz):
        s = f"{freqHz:09d}"
        timers.timedLog(f"CAT command: SET frequency")
        timers.timedLog(f"CAT: {s}")
        fBytes = b"".join(bytes([b]) for b in [16*int(s[7])+int(s[8]),16*int(s[5])+int(s[6]),16*int(s[3])+int(s[4]),16*int(s[1])+int(s[2]), int(s[0])])
        if(not self.serial_port): return
        self.sendCAT(b"".join([b'\x00', fBytes]))

    def setMode(self, md='USB', dat=False, filIdx = 1 ):
        timers.timedLog(f"CAT command: SET mode: {md} data:{dat} filter:{filIdx}")
        mdIdx = ['LSB','USB','AM','CW','RTTY','FM','WFM','CW-R','RTTY-R'].index(md)
        datIdx = 1 if dat else 0
        self.sendCAT(b''.join([b'\x26\x00', bytes([mdIdx]), bytes([datIdx]), bytes([filIdx]) ]) )

    def setPTTON(self):
        timers.timedLog(f"CAT command: PTT On")
        if(not self.serial_port): return
        self.sendCAT(b'\x1c\x00\x01')

    def setPTTOFF(self):
        timers.timedLog(f"CAT command: PTT Off")
        if(not self.serial_port): return
        self.sendCAT(b'\x1c\x00\x00')            

#icom = IcomCIV()
#icom.setPTTON()
#icom.setUSBD();
#icom.setFreqHz(14123450)


