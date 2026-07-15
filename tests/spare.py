
import numpy as np
import matplotlib.pyplot as plt
import threading, queue, time

SIZE = 200
import matplotlib.style as mplstyle
import matplotlib as mpl
mplstyle.use('fast')

bg = np.random.rand(SIZE,SIZE)

def sender():
    global msg_box_display_queue, bg
    x, y = SIZE*np.random.rand(50), SIZE*np.random.rand(50)
    for i in range(20):
        bg = np.random.rand(SIZE,SIZE)
        time.sleep(0.16)
        msg_box_display_queue.put({'x':x[i], 'y':y[i]})
    
class Msg_box():
    def __init__(self, message):
        from matplotlib.patches import Rectangle
        self.x, self.y = message['x'], message['y']
        rect = Rectangle((self.x, self.y), width=100, height=6, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.patch.set_visible(True)
        self.text_inst = ax.text(self.x, self.y, 'Testing text', fontsize='small', fontweight='bold', clip_on = True )
 
fig, ax = plt.subplots( figsize=(8,8) )
ax.set_xlim(0,SIZE)
ax.set_ylim(0,SIZE)


msg_box_display_queue = queue.Queue()
img = ax.imshow(bg)
threading.Thread(target = sender, daemon = True).start()
plt.pause(0.1)
#plt.ion()
while True:

    img.set_data(bg)

    while not msg_box_display_queue.empty():
        message = msg_box_display_queue.get()
        mb = Msg_box(message)

    t = time.time()
    fig.canvas.draw()
    print(time.time() - t)
    fig.canvas.flush_events()
    time.sleep(0.01)
