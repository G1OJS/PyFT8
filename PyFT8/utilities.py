import time
global t0
t0 = None

def tprint(text):
    global t0
    if(t0 is None): t0 = time.time()
    t = time.time() - t0
    print(f"{t:05.2f}s  {text}")
