import matplotlib.pyplot as plt
import pandas as pd

df_all = pd.read_csv('live_compare_stats.csv')

df = df_all[['Sinst','Sldpc','Sflip','Failed','Undecoded']]

# percentage version
df_pc = df.div(df.sum(axis=1), axis=0)

fig, axes = plt.subplots(4, 1, figsize=(8, 10), sharex=True)

cols = ['Teal','Lime','Green','Purple','Red']
df.plot.area(stacked=True, ax=axes[0], color = cols)
axes[0].set_title("Absolute counts per cycle")

df_pc.plot.area(stacked=True, ax=axes[1], color = cols)
axes[1].set_title("Percentage distribution per cycle")
axes[1].set_ylim(0, 1)   # % scale
axes[1].yaxis.set_major_formatter(lambda v, pos: f"{v*100:.0f}%")

df_times = df_all[['t_sync','t_demap','t_decode_s','t_decode_f']]
df_times.plot.area(stacked=True, ax = axes[2])
axes[2].set_title("Total time used per cycle")
axes[2].set_ylim(0, 15)

df_all.plot(y = ['Decoded'], ax = axes[3])
axes[3].set_title("Number of decode attempts")
axes[3].set_ylim(0, 1500)

plt.tight_layout()
plt.show()
