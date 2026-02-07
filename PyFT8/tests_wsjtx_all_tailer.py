import threading
import time

class Wsjtx_all_tailer:
    
    def __init__(self, on_decode, running = True, all_file = "C:/Users/drala/AppData/Local/WSJT-X/ALL.txt"):
        self.all_file = all_file
        self.on_decode = on_decode
        self.running = running
        threading.Thread(target = self.run).start()

    def run(self):
        def follow():
            with open(self.all_file, "r") as f:
                f.seek(0, 2)
                while self.running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    yield line.strip()
        for line in follow():
            ls = line.split()
            try:
                cs, freq, dt, snr = ls[0], int(ls[6]), float(ls[5]), int(ls[4])
                msg = f"{ls[7]} {ls[8]} {ls[9]}"
                td = f"{time.time() %60:4.1f}"
                self.on_decode({'cs':cs, 'decoder':'WSJTX', 'f':int(freq), 'msg':msg, 'dt':dt, 'snr':snr, 'td':td})
            except:
                print(f"Wsjtx_tailer error in line '{line}'")
