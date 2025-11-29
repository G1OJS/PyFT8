import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------


df = pd.read_csv('../success_fail_counts.csv')

print(df)

#cyc = df.query("cycle_str == '251129_121200' or cycle_str == '251129_121215'")
cyc = df

pd.set_option('display.max_columns', None)
print(cyc)

fig, ax = plt.subplots()

#ax.stackplot(cyc['unix_ts'], cyc['n_pending_demap'],cyc['n_demapped'],cyc['n_pending_ldpc'],cyc['n_ldpcd'])
ax.stackplot(cyc['unix_ts'], cyc['n_pending_demap'],cyc['n_demapped'])
plt.legend(loc='upper left')
plt.show()
