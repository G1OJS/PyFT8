
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

fig = plt.figure( figsize=(8,8) )

a = np.random.rand(500,500)
im = plt.imshow(a, interpolation='none', aspect='auto', vmin=0, vmax=1)

def animate_func(i):
    im.set_data(np.random.rand(500,500))
    return [im]

anim = animation.FuncAnimation(fig, animate_func, frames = range(100000), interval = 100)

plt.show()  # Not required, it seems!
