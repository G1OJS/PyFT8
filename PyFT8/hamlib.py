import socket
import subprocess
import threading
import time

class Rig_hamlib:
    def __init__(self, config):
        com = config['hamlib_rig']['port']
        s = config['hamlib_rig']['baud_rate']
        rigctld = config['hamlib_rig']['rigctld']
        rig = config['hamlib_rig']['model']
        host, port ="localhost", 4532
        cmd = f"{rigctld} -m {rig} -r /{com} -s {s}"
        threading.Thread(target = subprocess.run, args = (cmd,)).start()
        self.sock = socket.create_connection((host, port))

    def cmd(self, command):
        self.sock.sendall((command + "\n").encode())
        return self.sock.recv(1024).decode()

    def set_freq_Hz(self, hz):
        self.cmd(f"F {hz}")

    def ptt_on(self):
        self.cmd(f"T 1")

    def ptt_off(self):
        self.cmd(f"T 0")


if __name__ == '__main__':
    rig = Rig_hamlib()
    rig.set_freq_Hz(14074000)
    rig.ptt_on()
    time.sleep(0.1)
    rig.ptt_off()
