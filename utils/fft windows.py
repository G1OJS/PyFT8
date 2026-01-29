import numpy as np
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
n=256
w = np.kaiser(n,300)
wf = np.fft.fftshift(np.fft.fft(w, norm = 'ortho'))
print(wf.shape)
ax.plot(w)
ax.plot(np.abs(wf))
plt.show()
