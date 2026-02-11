import os
import numpy as np
import matplotlib.pyplot as plt

#pattern = '_cyclemgr_'
pattern = '_offline_'

data_table = {'P':{},'L':{},'W':{}}
folder = r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\tests\data\ft8_lib\20m_busy"
for filename in os.listdir(folder):
    if(filename.endswith("txt")):
        filepath = os.path.join(folder, filename)
        idx = ""
        if(pattern in filename): idx = "P"
        if('ft8_lib' in filename): idx = "L"
        if('wsjt' in filename): idx = "W"
        with open(filepath, 'r') as f:
            lines = f.readlines()
        if(idx != ""):
            test_no = int(filename.split("_")[1])
            data_table[idx][test_no] = {'n_decodes':len(lines), 'decodes':lines}


fig, ax = plt.subplots()
decoders = [d for d in data_table]
tests = [t for t in data_table['P']]
n_decodes = [[]] * len(tests)
for i, t in enumerate(tests):
    n_decodes[i] = [data_table[d][t]['n_decodes'] for d in decoders]
py = np.array([100*ns[0]/ns[2] for ns in n_decodes])
lb = np.array([100*ns[1]/ns[2] for ns in n_decodes])
tests = np.array(tests)

ax.bar(tests-0.5, py, width = 0.4, label = "PyFT8")
ax.bar(tests, lb, width = 0.4, label = "FT8_lib")
ax.legend()
ax.set_xlim(0,len(tests)+1)
ax.set_ylim(40,110)
ax.text(1,100, f"PyFT8 mean {np.mean(py):3.1f}%")
ax.text(1,96, f"FT8_lib mean {np.mean(lb):3.1f}%")
ax.set_xlabel("Test file number")
ax.set_ylabel("% of WSJT-X decodes")
fig.suptitle("PyFT8 and FT8_lib decodes as percentage of WSJT-X v2.7.0 in NORM mode")
plt.show()

