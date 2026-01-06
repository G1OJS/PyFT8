import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('live_compare_stats.csv')

df = df[df.columns[:6]]

df_pc = df.div(df.sum(axis=1), axis=0)

fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

cols = ['Teal','Lime','Green','Orange','Purple','Red']
df.plot.area(stacked=True, ax=axes[0], color = cols)
axes[0].set_title("Absolute counts per cycle")

df_pc.plot.area(stacked=True, ax=axes[1], color = cols)
axes[1].set_title("Percentage distribution per cycle")
axes[1].set_ylim(0, 1)   # % scale
axes[1].yaxis.set_major_formatter(lambda v, pos: f"{v*100:.0f}%")


plt.tight_layout()
plt.show()
