
import threading
import PyFT8.timers as timers
from PyFT8.comms_hub import config

def start_wsjtx_tailer(on_wsjtx_decode):
    threading.Thread(target=wsjtx_all_tailer, kwargs = ({'all_txt_path':config.wsjtx_all_file, 'on_wsjtx_decode':on_wsjtx_decode})).start()  

def wsjtx_all_tailer(all_txt_path, on_wsjtx_decode):
    def follow():
        with open(all_txt_path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    timers.sleep(0.2)
                    continue
                yield line.strip()
    for line in follow():
        ls = line.split()
        decode_dict = False
        try:
            decode_dict = {'decoder':'WSJTX', 'cyclestart_str':ls[0],'snr':ls[4], 'dt':ls[5], 'freq':ls[6], 'call_a':ls[7], 'call_b':ls[8], 'grid_rpt':ls[9]}
        except:
            pass
        if(decode_dict):
            on_wsjtx_decode(decode_dict)
