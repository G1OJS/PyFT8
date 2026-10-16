import threading, socket, json, time

class UdpComms:
    def __init__(self, ports = {'listen':None,'send':None}, rx_callback = None, remote_host = 'localhost'):
        self.ports = ports
        self.remote_host = remote_host
        self.rx_callback = rx_callback
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.ports['listen']:
            self._start_listener()

# senders ----------------------------------
    def udp_send_dict(self, msg_dict):
        self.udp_send_bytes(json.dumps(msg_dict).encode('utf-8'))

    def udp_send_bytes(self, msg_bytes):
        self.sock_send.sendto(msg_bytes, (self.remote_host, self.ports['send']))

# listener ---------------------------------
    def _start_listener(self):
        self.sock_listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_listen.settimeout(0.1)
        try:
            self.sock_listen.bind(('', self.ports['listen']))
        except:
            print("Couldn't open upd socket - is PyFT8 already running?")
            return
        threading.Thread(target = self._listen, daemon = True).start()

    def _listen(self):
        while self.sock_listen:
            rx_bytes = None
            try:
                rx_bytes, _ = self.sock_listen.recvfrom(1024)
            except:
                pass
            if rx_bytes:
                msg_dict = json.loads(rx_bytes.decode('utf-8'))
                self.rx_callback(msg_dict)

# ==================================================================================
