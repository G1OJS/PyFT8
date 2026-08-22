import numpy as np
import matplotlib.pyplot as plt

def read_cycles(filename):
    with open(filename) as f:
        rows = f.readlines()
        
    cycle_start_row_number = 0
    cycles = []
    cycle_number = None
    for row_number, row in enumerate(rows):
        fields = row.split()
        if cycle_number is None:
            cycle_number = fields[1]
        if cycle_number != fields[1]:
            cycles.append([r.split('~')[1].strip() for r in rows[cycle_start_row_number : row_number]] )
            cycle_number = fields[1]
            cycle_start_row_number = row_number
    return cycles

#files = ['WSJTx302_8_28_FAST.txt', 'WSJTx302_8_28_NORM.txt']
#files = ['PyFT8.txt', 'PyFT8_8_28_baseline.txt']
#files = ['PyFT8_8_28_baseline.txt', 'WSJTx302_8_28_FAST.txt']
files = ['PyFT8.txt', 'WSJTx302_8_28_FAST.txt']

a_cycles = read_cycles(files[0])
b_cycles = read_cycles(files[1])

a_only, b_only = 0, 0
for cycle_number, a_cycle_rows in enumerate(a_cycles):
    b_cycle_rows = b_cycles[cycle_number]
    print(f"\nCycle {cycle_number} =====================================")
    print(f"{'Common':30s} {'Only '+files[0]:30s} {'Only '+files[1]:30s}")
    tab = [[],[],[]]
    for msg in a_cycle_rows:
        if msg in b_cycle_rows:
            tab[0].append(msg)
        else:
            tab[1].append(msg)
            a_only += 1
    for msg in b_cycle_rows:
        if not msg in a_cycle_rows:
            tab[2].append(msg)
            b_only += 1 

    for i in range(len(tab[0])):
        col1 = tab[0][i]
        col2 = tab[1][i] if i < len(tab[1]) else ''
        col3 = tab[2][i] if i < len(tab[2]) else ''
        print(f"{col1:30s} {col2:30s} {col3:30s}")

print("\nTotals =====================================")
print(f"Only in {files[0]}: {a_only}")
print(f"Only in {files[1]}: {b_only}")
    
