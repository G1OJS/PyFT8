
import numpy as np
import matplotlib.pyplot as plt
import threading, queue, time
bg = np.random.rand(500,500)

def sender():
    global msg_box_display_queue, bg
    x, y = 500*np.random.rand(50), 500*np.random.rand(50)
    for i in range(50):
        bg = np.random.rand(500,500)
        time.sleep(0.01)
        msg_box_display_queue.put({'x':x[i], 'y':y[i]})
    
class Msg_box():
    def __init__(self, message):
        from matplotlib.patches import Rectangle
        self.x, self.y = message['x'], message['y']
        rect = Rectangle((self.x, self.y), width=40, height=40, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.patch.set_visible(True)

fig, ax = plt.subplots( figsize=(8,8) )
ax.set_xlim(0,500)
ax.set_ylim(0,500)


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
        
    fig.canvas.draw()
    fig.canvas.flush_events()
    time.sleep(0.01)
