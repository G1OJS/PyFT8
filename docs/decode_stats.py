import numpy as np
import matplotlib.pyplot as plt

with open('../success_fail_metrics.log') as f:
    with open('metrics.log', 'w') as f_o:
        for i, l in enumerate(f.readlines()):
            if(i==0):
                l = l.replace('{','').replace('}','').replace('c.','')
            else:
                l = l.replace('(','').replace(')','')
            f_o.write(l)
        

import pandas as pd
df = pd.read_csv('metrics.log', sep=r"\s+", header=0)


decoded = df['decoded'].values
llr_sd  = df['llr_sd'].values.astype(float)
score  = df['score'].values.astype(float)
snr  = df['snr'].values.astype(float)

def success_vs_bins(values, decoded, nbins=25):
    bins = np.linspace(min(values), max(values), nbins)
    digitized = np.digitize(values, bins)
    success = []
    centres = []
    for i in range(1, len(bins)):
        in_bin = decoded[digitized == i]
        if len(in_bin) > 0:
            success.append(in_bin.mean())
            centres.append((bins[i] + bins[i-1]) / 2)
    return np.array(centres), np.array(success)

llr_x, llr_y = success_vs_bins(llr_sd, decoded)
sco_x, sco_y = success_vs_bins(score, decoded)
snr_x, snr_y = success_vs_bins(snr, decoded)

plt.plot(llr_x, llr_y, marker='o', label="llr_sd")
plt.plot(sco_x, sco_y, marker='o', label="sync score")

plt.xlabel("Metric value")
plt.ylabel("Decode success rate")
plt.ylim(0,1)
plt.legend()
plt.grid(True)
plt.show()
