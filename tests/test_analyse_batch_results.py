import os
import numpy as np
import matplotlib.pyplot as plt

pattern = '_cyclemgr_'
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

def plot_snrs():
    fig, ax = plt.subplots()
    decoders = [d for d in data_table]
    tests = [t for t in data_table['P']]
    
    wsnr, psnr = [], []
    for t in tests:
        py_decodes = data_table['P'][t]['decodes']
        ws_decodes = data_table['W'][t]['decodes']
        for w in ws_decodes:
            m = [p for p in py_decodes if p.split()[5:] == w.split()[5:]]
            if(len(m)==1):
                wsnr.append(int(w.split()[1]))
                psnr.append(int(m[0].split()[1]))
    
    ax.scatter(wsnr, psnr)
    ax.set_xlabel("WSJT-X SNR")
    ax.axline((-30,-30),(30,30), linewidth=4, color='r')
    plt.show()

    
def plot_freqs():
    fig, ax = plt.subplots()
    decoders = [d for d in data_table]
    tests = [t for t in data_table['P']]
    
    wfrqs, pfrqs = [], []
    for t in tests:
        py_decodes = data_table['P'][t]['decodes']
        ws_decodes = data_table['W'][t]['decodes']
        for w in ws_decodes:
            m = [p for p in py_decodes if p.split()[5:] == w.split()[5:]]
            if(len(m)==1):
                wfrqs.append(int(w.split()[3]))
                pfrqs.append(int(m[0].split()[3]))

    pfrqs = np.array(pfrqs)    
    wfrqs = np.array(wfrqs)
    ax.scatter(wfrqs, pfrqs-wfrqs)
    ax.set_xlabel("WSJT-X Frequency")
    plt.show()
    
def plot_decode_counts():
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

#plot_freqs()
#plot_snrs()
plot_decode_counts()   
