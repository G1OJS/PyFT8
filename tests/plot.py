import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('live_compare_cycle_stats.csv')
ax = df.plot.area(stacked=True)

plt.show()
