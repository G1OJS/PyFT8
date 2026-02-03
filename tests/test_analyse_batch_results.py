import os
import numpy as np
import matplotlib.pyplot as plt

pattern = 'ldpc_30its_pyft8'
totals = []
folder = r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy"
for filename in os.listdir(folder):
    if(filename.endswith("txt")):
        filepath = os.path.join(folder, filename)
        idx = ""
        if(pattern in filename): idx = "PyFT8"
        if('ft8_lib' in filename): idx = "FT8_lib"
        if('wsjt' in filename): idx = "WSJT-X"
        with open(filepath, 'r') as f:
            lines = f.readlines()
        n_lines = len(lines)
        test_no = int(filename.split("_")[1])
        if(idx != ""):
            totals.append((test_no, idx, n_lines))

table = {}
for trow in totals:
    test = f"test_{trow[0]:02d}_"
    idx = trow[1]
    n = trow[2]
    if not test in table:
        table[test] = {"PyFT8": 0, "FT8_lib": 0, "WSJT-X": 0}
    table[test][idx] += n

tests = sorted(table.keys())
print(f"{'Test':<6} {'PyFT8':>8} {'FT8_lib':>10} {'WSJT-X':>8}")
print("-" * 46)

for t in tests:
    row = table[t]
    print(f"{t:<6} {row['PyFT8']:>8} {row['FT8_lib']:>10} {row['WSJT-X']:>8}")

wsjt = [table[t]["WSJT-X"]  for t in tests]
n_complete = np.count_nonzero(wsjt) - 1
lib  = [table[t]["FT8_lib"] for t in tests][:n_complete]
py   = [table[t]["PyFT8"]   for t in tests][:n_complete]
wsjt = wsjt[:n_complete]

for i in range(n_complete):
    print(i, lib[i], py[i], wsjt[i])
    py[i] = py[i] * 100 / wsjt[i]
    lib[i] = lib[i] * 100 / wsjt[i]

x = np.arange(n_complete)     
w = 0.25                      


plt.figure(figsize=(10,5))
plt.bar(x - w, py,   width=w, label="PyFT8")
plt.bar(x,     lib,  width=w, label="FT8_lib")


plt.xticks(x, x)
plt.xlabel("Test Number")
plt.ylabel("Number of Decodes")
plt.title("Number of Decodes PyFT8, FT8_lib, as percentage of WSJT-X v2.7.0 in NORM mode")
plt.legend()
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(fname = pattern+".png")
plt.show()

       
