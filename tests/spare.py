import numpy as np
import matplotlib.pyplot as plt
import pickle


fig, axs = plt.subplots(3,1, figsize = (8,10))

data = [0,0,0,0,0,1,2,1,3,2,5,4,3,4,5,6,7,9,9,9,1,9,8,1,9,7,3,4,3,4,2,1]
data = [0,0,0,0,0,9,9,9,9,9,9,9,9,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
c = np.ma.convolve(data, [1,1,1,1,1,1,1,1])/8
c = np.roll(c, -3)
axs[0].plot(data)
axs[0].plot(c)



plt.tight_layout()
plt.show()
