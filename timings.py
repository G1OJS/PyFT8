import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("timings.log", na_values=["None", " None"])

fig, ax = plt.subplots(figsize=(14, 7))
ax2 = ax.twinx()

def vbar(ax, x, t_start, t_end, color, lw=2, alpha=0.8, minbar = 0.05):
    if(t_end < t_start + minbar):
        t_end = t_start + minbar /2
        t_start = t_start - minbar /2
    ax.plot([x, x], [t_start, t_end], color=color, linewidth=lw, alpha=alpha)

pc_to_ldpc = []
pc_from_ldpc = []
n_cands = 0
n_to_ldpc =0
n_from_ldpc = 0
for _, row in df.iterrows():
    vbar(ax, row["id"], row["sync_returned"], row["demap_requested"], color = "tab:blue", lw=1, alpha = 0.2 )
    vbar(ax, row["id"], row["demap_requested"], row["demap_returned"], color = "tab:orange", lw=2.5, alpha = 0.4 )
    col, alpha = ('tab:green', 1) if(not pd.isnull(row["message_decoded"])) else ('tab:red',1)
    vbar(ax, row["id"], row["ldpc_requested"], row["ldpc_returned"], color = col, lw=2.5, alpha = alpha)
    if(not pd.isnull(row["demap_returned"])): n_cands +=1
    if(not pd.isnull(row["ldpc_requested"])): n_to_ldpc +=1
    pc_to_ldpc.append(100*n_to_ldpc / n_cands)
    if(not pd.isnull(row["ldpc_returned"])): n_from_ldpc +=1
    pc_from_ldpc.append(100*n_from_ldpc / n_cands)

ax.set_title("Candidate Timing with Pipeline Stage Durations")
ax.set_xlabel("Candidate ID")
ax.set_ylabel("Time within cycle (s)")
ax2.set_ylabel("Proportion of demapped sent/received ldpc")

from matplotlib.lines import Line2D
legend_els = [
    Line2D([0], [0], color="tab:blue", lw=1, alpha = 0.2 ),
    Line2D([0], [0], color="tab:orange", lw=2.5 , alpha = 0.4 ),
    Line2D([0], [0], color="tab:red", lw=2.5, alpha = 1  ),
    Line2D([0], [0], color="tab:green", lw=2.5, alpha = 1 )
]
ax.legend(legend_els,['await rx','demap','ldpc fail','ldpc success'])

ax2.plot(df['id'],pc_to_ldpc, c='tab:blue', label = '% to ldpc')
ax2.plot(df['id'],pc_from_ldpc, c='tab:orange', label = '% from ldpc')
ax2.legend()

ax2.set_ylim(0,100)

plt.grid(alpha=0.2)
plt.tight_layout()
plt.show()


