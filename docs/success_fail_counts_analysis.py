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


fig, ax = plt.subplots()

#ax.stackplot(cyc['unix_ts'], cyc['n_pending_demap'],cyc['n_demapped'],cyc['n_pending_ldpc'],cyc['n_ldpcd'])
#ax.plot(t, df['n_synced'], label = 'synced')
ax.plot(t, df['n_pending_demap'], label = 'pending demap')
ax.plot(t, df['n_demapped'], label = 'demapped')
#ax.plot(t, df['n_demapped_success'], label = 'demapped good llr_sd')
plt.legend(loc='upper left')
plt.show()
