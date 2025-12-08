import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("timings.log", na_values=["None", " None"])

fig, ax = plt.subplots(figsize=(14, 7))

def vbar(ax, x, t_start, t_end, color, lw=2, alpha=0.8, minbar = 0.05):
    if(t_end < t_start + minbar):
        t_end = t_start + minbar /2
        t_start = t_start - minbar /2
    ax.plot([x, x], [t_start, t_end], color=color, linewidth=lw, alpha=alpha)

for _, row in df.iterrows():
    vbar(ax, row["id"], row["sync_returned"], row["demap_requested"], color = "tab:blue", lw=1, alpha = 0.2 )
    vbar(ax, row["id"], row["demap_requested"], row["demap_returned"], color = "tab:orange", lw=2.5, alpha = 0.4 )
    col, alpha = ('tab:green', 1) if(not pd.isnull(row["message_decoded"])) else ('tab:grey',0.4)
    vbar(ax, row["id"], row["ldpc_requested"], row["ldpc_returned"], color = col, lw=2.5, alpha = alpha)

plt.title("Candidate Timing with Pipeline Stage Durations")
plt.xlabel("Candidate ID")
plt.ylabel("Time within cycle (s)")
#ax.set_xlim(0,5000)
#ax.set_ylim(11,)

from matplotlib.lines import Line2D
legend_els = [
    Line2D([0], [0], color="tab:blue", lw=1, alpha = 0.2 ),
    Line2D([0], [0], color="tab:orange", lw=2.5 , alpha = 0.4 ),
    Line2D([0], [0], color="tab:grey", lw=2.5, alpha = 0.4  ),
    Line2D([0], [0], color="tab:green", lw=2.5, alpha = 1 )
]

ax.legend(legend_els,['await rx','demap','ldpc failure', 'ldpc success'], loc='upper right')


plt.grid(alpha=0.2)
plt.tight_layout()
plt.show()


