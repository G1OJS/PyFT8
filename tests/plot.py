import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('live_compare_cycle_stats.csv')

df_pc = df.divide(df.sum(axis=1), axis=0)

df.plot.area(stacked = True)
    

plt.show()
