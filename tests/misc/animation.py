import numpy as np
import time, queue
import threading
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation

q = queue.Queue()

def counter():
    global q
    while True:
        time.sleep(1)
        for i in range(10):
            time.sleep(0.1)
            q.put((i, time.time()))

def onclick(event):
    print("Click")

def an_cb(frame):
    while not q.empty():
        time.sleep(0.1)
        tsend = q.get()
        print(tsend)
        txt.set_text(time.time()-tsend[1])
    return [txt]

fig, ax = plt.subplots()
txt = ax.text(0.5,0.5, 'Text')
tsend = 0
threading.Thread(target = counter, daemon = True).start()

#cid = fig.canvas.mpl_connect('button_press_event', onclick)
ani = FuncAnimation(fig, an_cb, interval = 100, frames=(100000), blit=True)
plt.show()
