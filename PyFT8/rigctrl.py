import time, socket, subprocess, threading

class Rig_hamlib:
    def __init__(self, config):
        com = config['hamlib_rig']['port']
        s = config['hamlib_rig']['baud_rate']
        rigctld = config['hamlib_rig']['rigctld']
        rig = config['hamlib_rig']['model']
        host, port ="localhost", 4532
        cmd = f"{rigctld} -m {rig} -r {com} -s {s}"
        if not self.create_socket(host, port):
            threading.Thread(target = subprocess.run, args = (cmd,)).start()
            time.sleep(0.5)
            self.create_socket(host, port)
        self.set_mode("PKTUSB")

    def create_socket(self, host, port):
        try:
            self.sock = socket.create_connection((host, port))
        except:
            return False
        return True

    def cmd(self, command):
        self.sock.sendall((command + "\n").encode())
        return self.sock.recv(1024).decode()

    def set_mode(self, mode):
        self.cmd(f"M {mode} 0")

    def set_freq_Hz(self, hz):
        self.cmd(f"F {hz}")

    def ptt_on(self):
        self.cmd(f"T 1")

    def ptt_off(self):
        self.cmd(f"T 0")


