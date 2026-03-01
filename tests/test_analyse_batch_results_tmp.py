import os
import numpy as np
import matplotlib.pyplot as plt

pattern = '_cyclemgr_'
#pattern = '_offline_'

def readfiles(folder, pattern, idx):
    tests = {}
    for filename in os.listdir(folder):
        if(filename.endswith("txt") and pattern in filename):
            filepath = os.path.join(folder, filename)
            with open(filepath, 'r') as f:
                lines = f.readlines()
            test_no = int(filename.split("_")[1])
            tests[test_no] = lines
    data_table[idx] = tests

data_table = {}
readfiles(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\results\ft8_lib_20m_busy_PyFT8", "test", 0)
readfiles(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\results\ft8_lib_20m_busy", "test", 1)


fig, ax = plt.subplots()
x,y, c = [],[],[]
total_missing = 0

for test_no in range(1,39):
    main, curr_ends, curr = [],[],[]
    for l in data_table[1][test_no]:
        curr.append(l)
        curr_ends.append(l[22:].strip())
   # print(curr_ends)
    for l in data_table[0][test_no]:
        msg = ' '.join(l.split()[5:8])
        #print(msg, msg in curr_ends)
        c.append('blue' if msg in curr_ends else 'red')
        x.append(float(l[11:14]))
        y.append(test_no)
        total_missing += (0 if msg in curr_ends else 1)
    print(total_missing)

ax.scatter(x,y,color=c)

plt.show()

