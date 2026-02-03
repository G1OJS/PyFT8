import os


totals = []
folder = r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy"
for filename in os.listdir(folder):
    if(filename.endswith("txt")):
        filepath = os.path.join(folder, filename)
        if('pyft8' in filename): idx = "PyFT8"
        if('ft8_lib' in filename): idx = "FT8_lib"
        if('wsjt' in filename): idx = "WSJT-X"
        with open(filepath, 'r') as f:
            lines = f.readlines()
        n_lines = len(lines)
        test_no = int(filename.split("_")[1])
        totals.append((test_no, idx, n_lines))

from collections import defaultdict

# totals = [(test_no, decoder, n_lines), ...]

table = defaultdict(lambda: {"PyFT8": 0, "FT8_lib": 0, "WSJT-X": 0})

for test_no, decoder, count in totals:
    table[test_no][decoder] = count

# Sort by test number
tests = sorted(table.keys())

# Print header
print(f"{'Test':<6} {'PyFT8':>8} {'FT8_lib':>10} {'WSJT-X':>8} {'Best':>8}")
print("-" * 46)

for t in tests:
    row = table[t]
    best = max(row, key=row.get)
    print(f"{t:<6} {row['PyFT8']:>8} {row['FT8_lib']:>10} {row['WSJT-X']:>8} {best:>8}")

import numpy as np
import matplotlib.pyplot as plt

tests = sorted(table.keys())

py   = [table[t]["PyFT8"]   for t in tests]
lib  = [table[t]["FT8_lib"] for t in tests]
wsjt = [table[t]["WSJT-X"]  for t in tests]

x = np.arange(len(tests))     # test positions
w = 0.25                      # bar width

plt.figure(figsize=(10,5))
plt.bar(x - w, py,   width=w, label="PyFT8")
plt.bar(x,     lib,  width=w, label="FT8_lib")
plt.bar(x + w, wsjt, width=w, label="WSJT-X")

plt.xticks(x, tests)
plt.xlabel("Test Number")
plt.ylabel("Number of Decodes")
plt.title("Decoder Performance per Test")
plt.legend()
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()

       
