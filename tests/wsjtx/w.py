import win32api,win32process
win32process.SetPriorityClass(win32api.GetCurrentProcess(), win32process.HIGH_PRIORITY_CLASS)

import time
from subprocess import Popen, PIPE, CalledProcessError

finished_audio = False

def do_test(wav_range = None):

    ws_cycle = ['', 0]
    with open('wsjtx.txt','w') as f:
        f.write('')

    ws_times = []
    cycle = 0
    decode_count = 0
    if wav_range:
        for idx in range(*wav_range):
            cycle += 1
            t_start = time.time()
            with Popen(["w.exe", f"{wav_folder}/test_{idx:02d}.wav"], stdout=PIPE, bufsize=1, universal_newlines=True) as p:
                for line in p.stdout:
                    ls = line.split()
                    t = 15*cycle + time.time()-t_start
                    msg = ls[3:]
                    dt, f = float(ls[0]), float(ls[1]) 
                    decode_count += 1
                    ws_info  = f"{decode_count:03d} {cycle:3d} {t:06.2f} +24 {dt:+05.3f} {f:07.2f} ~ {' '.join(msg)}"
                    with open('wsjtx.txt', 'a') as f:
                        f.write(f"{ws_info}\n")
                    print(ws_info)

wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"

do_test([8,28])





