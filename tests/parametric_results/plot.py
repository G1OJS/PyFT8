import matplotlib.pyplot as plt

fig, ax = plt.subplots()

t = [0.7, 0.8, 0.9, 1.4, 2.1, 2.3, 2.4]
pc = [61.7, 65.6, 68.6, 70.6, 71.5, 71.9, 71.9]
txts= ['25','30','35','40','45','50','55']
ax.plot(pc,t, marker="o", label = "OSD off")
for i, txt in enumerate(txts):
    ax.annotate(txt, (pc[i]+0.02, t[i]))

t = [0.8, 1.0, 2.4]
pc = [61.7, 65.9, 69.9]
txts= ['25','30','35']
ax.plot(pc,t, marker="o", label = "OSD nc<20")
for i, txt in enumerate(txts):
    ax.annotate(txt, (pc[i]+0.02, t[i]))


    
ax.set_xlim(60,80)
ax.set_ylim(0.5,3)
ax.set_ylabel("Decoding time used per cycle, s")
ax.set_xlabel("Percent of WSJT-X decodes")
ax.legend()
fig.suptitle("% of WSJT-X decodes vs decode time per cycle")
plt.show()
