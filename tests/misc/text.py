import matplotlib.pyplot as plt
fig, ax = plt.subplots()
arts = []
for i in range(10):
    t = ax.text(0.5,0.5,f"hi {i}")
    arts.append(t)

for a in arts:
    a.remove()
plt.show()
