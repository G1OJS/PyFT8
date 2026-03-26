import socket
import subprocess
import threading
import time

class Hamlib:
    def __init__(self, host="localhost", port=4532, rigctld = "C:/WSJT/wsjtx/bin/rigctld-wsjtx", rig = 3070, com = "COM4", s=9600):
        cmd = f"{rigctld} -m {rig} -r /{com} -s {s}"
        threading.Thread(target = subprocess.run, args = (cmd,)).start()
        self.sock = socket.create_connection((host, port))

    def cmd(self, command):
        self.sock.sendall((command + "\n").encode())
        return self.sock.recv(1024).decode()

    def get_freq(self):
        return int(self.cmd("f"))

    def set_freq(self, hz):
        self.cmd(f"F {hz}")

    def ptt(self, state):
        self.cmd(f"T {1 if state else 0}")


rig = Hamlib()
rig.set_freq(14074000)
rig.ptt(True)
time.sleep(0.1)
rig.ptt(False)
