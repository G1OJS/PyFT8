
class IC_7100:
    import serial

    def __init__(self, verbose = False, port = 'COM5', baudrate = 9600):
        self.serial_port = False
        self.verbose = verbose
        try:
            self.serial_port = self.serial.Serial(port = port, baudrate = baudrate, timeout = 0.1)
            if (self.serial_port):
                print(f"Connected to {port}")
        except IOError:
            print(f"Couldn't connect to {port} - running without CI-V")

    def decode_twoBytes(self, twoBytes):
        if(len(twoBytes)==2):
            n1 = int(twoBytes[0])
            n2 = int(twoBytes[1])
            return  n1*100 + (n2//16)*10 + n2 %16
        
    def sendCAT(self, cmd):
        if(not self.serial_port): return
        self.serial_port.reset_input_buffer()
        msg = b'\xfe\xfe\x88\xe0' + cmd + b'\xfd'
        if(self.verbose):
            print(f"[CAT] send {msg.hex(' ')}")
        self.serial_port.write(msg)
        resp = self.serial_port.read_until(b'\xfd')
        resp = self.serial_port.read_until(b'\xfd')
        if(self.verbose):
            print(f"[CAT] response {resp.hex(' ')}")
        return resp

    def setFreqHz(self, freqHz):
        s = f"{freqHz:09d}"
        print(f"[CAT] SET frequency")
        print(f"[CAT] {s}")
        fBytes = b"".join(bytes([b]) for b in [16*int(s[7])+int(s[8]),16*int(s[5])+int(s[6]),16*int(s[3])+int(s[4]),16*int(s[1])+int(s[2]), int(s[0])])
        self.sendCAT(b"".join([b'\x00', fBytes]))

    def setMode(self, md='USB', dat=False, filIdx = 1 ):
        if(self.verbose):
            print(f"[CAT] SET mode: {md} data:{dat} filter:{filIdx}")
        mdIdx = ['LSB','USB','AM','CW','RTTY','FM','WFM','CW-R','RTTY-R'].index(md)
        datIdx = 1 if dat else 0
        self.sendCAT(b''.join([b'\x26\x00', bytes([mdIdx]), bytes([datIdx]), bytes([filIdx]) ]) )

    def setPTTON(self, PTT_on = '1C 00 01'):
        if(self.verbose):
            print(f"[CAT] PTT On")
        self.sendCAT(PTT_on)

    def setPTTOFF(self, PTT_off = '1C 00 00'):
        if(self.verbose):
            print(f"[CAT] PTT Off")
        self.sendCAT(PTT_off)

    def getSWR(self):
        resp = False
        self.setMode("RTTY")
        self.setPTTON()
        timers.sleep(0.05)
        if(self.verbose):
            print(f"CAT command: get SWR")
        resp = self.sendCAT(b'\x15\x12')
        self.setPTTOFF()
        self.setMode(md="USB", dat = True, filIdx = 1)
        resp_decoded = self.decode_twoBytes(resp[-3:-1])
        if(resp_decoded):
            return int(resp_decoded)

    def getPWR(self):
        resp = False
        if(self.verbose):
            print(f"CAT command: get PWR")
        resp = self.sendCAT(b'\x14\x0A')
        resp_decoded = self.decode_twoBytes(resp[-3:-1])
        if(resp_decoded):
            return int(resp_decoded)


