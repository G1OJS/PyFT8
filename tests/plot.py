import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('live_compare_cycle_stats.csv')
cols = list(df.columns)
cols.reverse()
df = df[cols]
colours = ('green','orange','blue')

# percentage version
df_pc = df.div(df.sum(axis=1), axis=0)

fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

df.plot.area(stacked=True, ax=axes[0], color = colours)
axes[0].set_title("Absolute counts per cycle")

df_pc.plot.area(stacked=True, ax=axes[1], color = colours)
axes[1].set_title("Percentage distribution per cycle")
axes[1].set_ylim(0, 1)   # % scale
axes[1].yaxis.set_major_formatter(lambda v, pos: f"{v*100:.0f}%")

plt.tight_layout()
plt.show()
