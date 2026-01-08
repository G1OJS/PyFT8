import matplotlib.pyplot as plt
import pandas as pd

folder = "."
stats_file = f"{folder}/compare_stats.csv"
screen_file = f"{folder}/compare_screen.csv"
decodes_file = f"{folder}/compare_decodes.csv"


fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

cols = ['#06c92e','#857277','#c47fb6','#afffb2','#c4bbb6','#ebd2f3','White']

df = pd.read_csv(stats_file)
df = df[df.columns[:6]]
axes[0].set_title("Absolute counts per cycle")
p = df.plot.area(stacked=True, ax=axes[0], color = cols)
axes[1].set_title("Percentage distribution per cycle")
df_pc = df.div(df.sum(axis=1), axis=0)
df_pc.plot.area(stacked=True, ax=axes[1], color = cols)
axes[1].set_ylim(0, 1) 
axes[1].yaxis.set_major_formatter(lambda v, pos: f"{v*100:.0f}%")


fig, axes = plt.subplots()
w,p = [],[]
with open(decodes_file, "r") as f:
    for l in f.readlines():
        n,d = l.split(",")
        w.append(int(n))
        if('True' in d):
            p.append(int(n))


axes.hist(w, bins = range(50), label = "WSJTX",
        cumulative=-1, density = True, color = 'purple', alpha = 0.8)
axes.hist(p, bins = range(50), label = "PyFT8",
        cumulative=-1, density = True, color = 'green', alpha = 0.8)
axes.set_xlabel("Initial ncheck")
axes.set_ylabel("Fraction of decodes (cumulative)")
axes.legend()


plt.tight_layout()
plt.show()
