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
x,y = [],[]

for test_no in range(1,2):
    main, curr = [],[]
    for l in data_table[0][test_no]:
        main.append(l[22:])
    for l in data_table[1][test_no]:
        curr.append(l[22:])
    for l in set(main).difference(curr):
        print(l)
        
ax.scatter(x,y)

plt.show()

