import matplotlib.pyplot as plt
import pandas as pd


folder = "."
stats_file = f"{folder}/compare_stats.csv"
screen_file = f"{folder}/compare_screen.csv"
decodes_file = f"{folder}/compare_decodes.csv"

df = pd.read_csv(stats_file)
success = df[df.columns[:3]].sum(axis=1)
dfcols = df.columns[:7]
df_pc = df[dfcols].div(df[dfcols].sum(axis=1), axis=0)
success_pc = df_pc[df.columns[:3]].sum(axis=1)

fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
cols = ['#1E88E5','#2E7D32','#6A1B9A','#90CAF9','#A5D6A7','#ebd2f3','red']

axes[0].set_title("Absolute counts per cycle")
x = df.index
ys = [df[col].values for col in df.columns[:7]]
axes[0].stackplot(x,ys,labels = df.columns, colors = cols)
axes[0].plot(x, success, color="black", lw=1.2)
axes[0].plot(x, success, color="#1B5E20", lw=2.2)
axes[0].legend()

axes[1].set_title("Percentage distribution per cycle")
ys = [df_pc[col].values for col in df_pc.columns[:7]]
axes[1].stackplot(x,ys,labels = df.columns, colors = cols)
axes[1].plot(x, success_pc, color="black", lw=1.2)
axes[1].plot(x, success_pc, color="#1B5E20", lw=2.2)

axes[1].yaxis.set_major_formatter(lambda v, pos: f"{v*100:.0f}%")
axes[1].legend()

fig, axes = plt.subplots(2,1)
w,p = [],[]
with open(decodes_file, "r") as f:
    for l in f.readlines():
        n,d = l.split(",")
        w.append(int(n))
        if('True' in d):
            p.append(int(n))

for i in [0,1]:
    axes[i].hist(w, bins = range(60), label = "WSJTX",
            cumulative = -i, color = '#D32F2F', alpha = 0.8, lw=0.5, edgecolor = "black")
    axes[i].hist(p, bins = range(60), label = "PyFT8",
            cumulative = -i, color = '#388E3C', alpha = 0.8, lw=0.5, edgecolor = "black")
    axes[i].set_xlabel("Initial ncheck")
    axes[i].set_ylabel(f"Number of decodes{' (cumulative)' if i>0 else ''}")
    axes[i].legend()


plt.tight_layout()
plt.show()
