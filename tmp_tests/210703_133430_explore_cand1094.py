import matplotlib.pyplot as plt
import pickle

fig, ax = plt.subplots()

with open('cand1094_real.pkl', 'rb') as f:
    cr = pickle.load(f)

with open('cand1094_sim.pkl', 'rb') as f:
    cs = pickle.load(f)

ax.plot(cr.llr)
ax.plot(cs.llr/5)

plt.show()
