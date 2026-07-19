
import numpy as np
import matplotlib.pyplot as plt
import time
SIZE = 500

fig, ax = plt.subplots( figsize=(8,8) )
ax.set_xlim(0,SIZE)
ax.set_ylim(0,SIZE)
plt.show(block = False)

arts = []

from matplotlib.patches import Rectangle
for i in range(10):
    x, y = SIZE*np.random.rand(1)[0], SIZE*np.random.rand(1)[0]
    rect = Rectangle((x, y), width=100, height=6, alpha=0.6, edgecolor='lime', lw=2)
    art = ax.add_patch(rect)
    arts.append(art)
    ax.draw_artist(art)
fig.canvas.update()
fig.canvas.flush_events()
    
time.sleep(1)
for a in arts:
    a.remove()
plt.pause(0.001)

