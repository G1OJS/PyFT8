import serial, time

class Rig:

    def __init__(self, config, verbose = False):
        self.serial_port = False
        self.port = config['rig']['port']
        self.baud_rate = config['rig']['baud_rate']
        self.ptt_on_cmd = self.parse_configstr(config['rig']['ptt_on_command']) if config['rig']['ptt_on_command']else None
        self.ptt_off_cmd = self.parse_configstr(config['rig']['ptt_off_command']) if config['rig']['ptt_off_command'] else None
        self.set_freq_cmd = self.parse_configstr(config['rig']['set_freq_command']) if config['rig']['set_freq_command'] else None
        self.set_freq_value = config['rig']['set_freq_value'] if config['rig']['set_freq_value'] else None
        self.verbose = verbose

    def parse_configstr(self, configstr):
        if "." in configstr:
            hexstr = configstr.replace(".", "")
            return bytearray.fromhex(hexstr)
        else:
            return bytearray(configstr.encode())
        
    def vprint(self, text):
        if self.verbose:
            print(text)

    def _sendCAT(self, msg):
        try:
            self.serial_port = serial.Serial(port = self.port, baudrate = self.baud_rate, timeout = 0.1)
        except Exception as e:
            print(f"[CAT] couldn't open {self.port}: {e}")
        if (self.serial_port):
            self.serial_port.reset_input_buffer()
            self.vprint(f"[CAT] send {msg.hex(' ')}")
            try:
                self.serial_port.write(msg)
                time.sleep(0.05)
                self.serial_port.close()
            except Exception as e:
                print(f"[CAT] couldn't send CAT command {msg} on {self.port}: {e}")

    def set_freq_Hz(self, freqHz):
        if self.set_freq_cmd and self.set_freq_value:
            self.vprint(f"[CAT] SET frequency to {freqHz} Hz")
            start, length, fmt, mult, offset = self.set_freq_value.split("|")
            start, length, mult, offset = int(start), int(length), int(mult), int(offset)
            fVal = freqHz * mult + offset
            nDigits = length if fmt == "text" else 2*length
            s = f"{fVal:0{nDigits}d}"
            if fmt=='text':
                fBytes = s.encode()
            else:
                pairs = [(int(s[i]) << 4) | int(s[i+1]) for i in range(0, len(s), 2)]
                if fmt == "vfBcdLU":
                    fBytes = bytes(pairs[::-1])
                else:
                    fBytes = bytes(pairs)
            cmd = bytearray(self.set_freq_cmd)
            cmd[start:start+length] = fBytes
            if fmt.startswith("vfBcd"):  # CI-V
                cmd = b'\x00' + cmd
            self._sendCAT(cmd)

    def ptt_on(self):
        if self.ptt_on_cmd:
            self.vprint(f"[CAT] PTT On")
            self._sendCAT(self.ptt_on_cmd)

    def ptt_off(self):
        if self.ptt_off_cmd:
            self.vprint(f"[CAT] PTT Off")
            self._sendCAT(self.ptt_off_cmd)

