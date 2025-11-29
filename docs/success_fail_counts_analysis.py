import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------


df = pd.read_csv('../success_fail_counts.csv')

print(df.columns)
t = df['unix_ts'] 
t -=t[np.argmin(t %15)]

fig, axs = plt.subplots(2,2)

axs[0,0].plot(t, df['n_synced'], label = 'synced')
axs[0,0].plot(t, df['n_pending_demap'], label = 'pending demap')
axs[0,0].plot(t, df['n_demapped'], label = 'demapped')
axs[0,0].legend()

axs[1,0].plot(t, df['n_demapped'], label = 'demapped')
axs[1,0].plot(t, df['n_demapped_success'], label = 'demapped good llr_sd')
axs[1,0].plot(t, df['n_pending_ldpc'], label = 'pending ldpc')
axs[1,0].legend()

axs[0,1].plot(t, df['n_ldpcd'], label = 'ldpc done')
axs[0,1].plot(t, df['n_decoded'], label = 'decodes')
axs[0,1].plot(t, df['n_unique'], label = 'unique decodes')
axs[0,1].legend()

pc_decoded = df['n_decoded']/df['n_ldpcd']
axs[1,1].plot(t, pc_decoded, label = 'ldpc success rate')
axs[1,1].legend()

plt.show()
