import datetime

class IcomCIV:
    import serial

    def __init__(self, port='COM4', baudrate=9600, timeout=0.1):
        try:
            self.serial_port = self.serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
            if (self.serial_port):
                self.debug(f"Connected to {port}")
        except IOError:
            print(f"Couldn't connect to {port} - running without CI-V")    
            
    def debug(self, txt):
        if("Received" in txt):
            print()
        t = datetime.datetime.now(datetime.timezone.utc)
        logstr = f"{t.strftime("%H:%M:%S")}: {txt}"
        print(logstr)
        with open('controller_session.log','a') as f:
            f.write(logstr+'\n')
        
    def sendCAT(self, cmd):
        msg = b"".join([b'\xfe\xfe\x88\xe0', cmd, b'\xfd'])
        self.debug(f"CAT: {msg}")
        self.serial_port.write(msg)

    def getFreqHz(self):
        while self.serial_port.read():
            pass
        self.debug(f"CAT command: get frequency")
        self.sendCAT(b'\x03')
        resp = self.serial_port.read_until()
        self.debug(f"CAT: Icom responded with {resp}")
        if(len(resp)<10):
            return False
        return int("".join(f"{(b >> 4) & 0x0F}{b & 0x0F}" for b in reversed(resp[11:16])))

    def setFreqHz(self, freqHz):
        s = f"{freqHz:09d}"
        self.debug(f"CAT command: SET frequency")
        self.debug(f"CAT: {s}")
        fBytes = b"".join(bytes([b]) for b in [16*int(s[7])+int(s[8]),16*int(s[5])+int(s[6]),16*int(s[3])+int(s[4]),16*int(s[1])+int(s[2]), int(s[0])])
        self.sendCAT(b"".join([b'\x00', fBytes]))

    def setMode(self, md='USB', dat=False, filIdx = 1 ):
        self.debug(f"CAT command: SET mode: {md} data:{dat} filter:{filIdx}")
        mdIdx = ['LSB','USB','AM','CW','RTTY','FM','WFM','CW-R','RTTY-R'].index(md)
        datIdx = 1 if dat else 0
        self.sendCAT(b''.join([b'\x26\x00', bytes([mdIdx]), bytes([datIdx]), bytes([filIdx]) ]) )

    def setPTTON(self):
        self.debug(f"CAT command: PTT On")
        self.sendCAT(b'\x1c\x00\x01')

    def setPTTOFF(self):
        self.debug(f"CAT command: PTT Off")
        self.sendCAT(b'\x1c\x00\x00')            

#icom = IcomCIV()
#icom.setPTTON()
#icom.setUSBD();
#icom.setFreqHz(14123450)


