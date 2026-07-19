
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import time
import threading
SIZE = 1000

def thread1():
    dat = np.random.rand(SIZE, SIZE)
    while True:
        time.sleep(0.1)
        dat = ( dat * dat )%1


def oncanvasclick(args):
    t = time.time()
    print(t %60)

fig, ax = plt.subplots( figsize=(8,8) )
ax.set_xlim(0,SIZE)
ax.set_ylim(0,SIZE)
threading.Thread(target = thread1, daemon = True).start()
plt.show(block = False)

dat = np.random.rand(SIZE, SIZE)
img = ax.imshow(dat)
plt.pause(0.1)
cid = fig.canvas.mpl_connect('button_press_event', oncanvasclick)
while True:
    time.sleep(0.1)
    img.set_data(np.random.rand(SIZE, SIZE))
    plt.pause(0.2)

    


