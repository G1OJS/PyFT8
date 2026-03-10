"""
    Modify this code to drive your particular rig.
    
    This example is the code I use to control my IC-7100.
    The changes you will need to make are the serial port and baud rate,
    the internal functions (_xxxxx) if your rig is not Icom,
    and the commands to set ptt on and off and to set frequency.
    
"""
    
class Rig:
    import serial, time

    def __init__(self, verbose = False, port = 'COM4', baudrate = 9600):
        self.serial_port = False
        self.port = port
        self.baudrate = baudrate
        self.verbose = verbose

    def vprint(self, text):
        if self.verbose:
            print(text)

    def connect(self):
        try:
            self.serial_port = self.serial.Serial(port = self.port, baudrate = self.baudrate, timeout = 0.1)
            if (self.serial_port):
                self.vprint(f"Connected to {self.port}")
        except IOError:
            print(f"Couldn't connect to {self.port}")

    def _decode_twoBytes(self, twoBytes):
        if(len(twoBytes)==2):
            n1 = int(twoBytes[0])
            n2 = int(twoBytes[1])
            return  n1*100 + (n2//16)*10 + n2 %16
        
    def _sendCAT(self, cmd):
        self.connect()
        try:
            self.serial_port.reset_input_buffer()
            msg = b'\xfe\xfe\x88\xe0' + cmd + b'\xfd'
            self.vprint(f"[CAT] send {msg.hex(' ')}")
            self.serial_port.write(msg)
            resp = self.serial_port.read_until(b'\xfd')
            resp = self.serial_port.read_until(b'\xfd')
            self.vprint(f"[CAT] response {resp.hex(' ')}")
            self.serial_port.close()
            return resp
        except:
            print("couldn't send command")

    def PyFT8_set_freq_Hz(self, freqHz):
        s = f"{freqHz:09d}"
        self.vprint(f"[CAT] SET frequency")
        self.vprint(f"[CAT] {s}")
        fBytes = b"".join(bytes([b]) for b in [16*int(s[7])+int(s[8]),16*int(s[5])+int(s[6]),16*int(s[3])+int(s[4]),16*int(s[1])+int(s[2]), int(s[0])])
        self._sendCAT(b"".join([b'\x00', fBytes]))

    def PyFT8_ptt_on(self, PTT_on = b'\x1c\x00\x01'):
        self.vprint(f"[CAT] PTT On")
        self._sendCAT(PTT_on)

    def PyFT8_ptt_off(self, PTT_off = b'\x1c\x00\x00'):
        self.vprint(f"[CAT] PTT Off")
        self._sendCAT(PTT_off)

