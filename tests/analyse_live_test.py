import numpy as np

def plot_staircase(defs):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import AutoMinorLocator, MultipleLocator
    fig, ax = plt.subplots(figsize = (9,9))
    ax.yaxis.set_label_position("right")
    ax.xaxis.set_major_locator(MultipleLocator(15))
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(100))
    ax.yaxis.set_minor_locator(MultipleLocator(25))
    plt.grid(which = 'major', axis = 'x')
    plt.grid(which = 'major', axis = 'y')
    ax.yaxis.tick_right()
    ax.set_xlabel("Time, seconds")
    ax.set_ylabel("Cumulative decodes (unique per cycle)")
    fig.suptitle("Cumulative decode count against time\nPyFT8 vs WSJT-x")

    for d in defs:
        with open(d[0], 'r') as f:
            lines = f.readlines()
            times = [float(l.split()[2]) for l in lines]
            ax.plot(times, np.array(range(len(times))), label = d[1], color = d[2], marker = 'o', markersize = 3)
    ax.plot(ft8_lib_times, ft8_lib_counts, label = 'FT8_lib', color = 'pink', marker = 'o', markersize = 3)
    ax.legend()
    plt.show()

def list_methods(file):
    with open(file, 'r') as f:
        lines = f.readlines()

    counter = {}
    for l in lines:
        cat = l.split()[3]
        if cat not in counter:
            counter[cat]=0
        counter[cat] +=1

    def sortorder(cv):
        v = 0
        if 'grid' in cv[0]: v += 10000
        if 'NoAP' in cv[0]: v +=  9000
        if 'CQ' in cv[0]: v +=  8000
        if 'LDPC_OSD' in cv[0]: v -= 100000
        v += cv[1]
        return v

    catvals = []
    for c in counter.keys():
        catvals.append((c, counter[c]))
    catvals.sort(key = lambda cv: -sortorder(cv))

    print(f"\nBreakdown for '{file}'")
    for l in catvals:
        print(f"{l[0]:30s} {l[1]:>3d}")
    print(f"{'Total':>30s} {len(lines)}")



list_methods('PyFT8_8_28_baseline.txt')
list_methods('PyFT8.txt')

ft8_lib_per_file = [18,19,12,17,20,21,19,19,18,18,19,15,21,16,21,17,19,17,21,17,19,19,19,20,20,18,20,16,18,19,20,22,19,17,19,16,16,13]
ft8_lib_counts = []
n = 0
for i in range(8, 28):
    ft8_lib_counts.append(n)
    n += ft8_lib_per_file[i]
ft8_lib_times = 15 + 15*np.arange(0,len(ft8_lib_counts))
plot_staircase([('PyFT8_8_28_baseline.txt', 'PyFT8-baseline', 'green'),
                ('WSJTx302_8_28_FAST.txt', 'WSJT-x_3.0.2_FAST', 'blue'),
                ('WSJTx302_8_28_NORM.txt', 'WSJT-x_3.0.2_NORM', 'purple'),
                ('PyFT8.txt', 'PyFT8', 'orange')])

#plot_staircase([
#                ('WSJTx.txt', 'WSJT-x_3.0.2_FAST', 'blue'),
#                ('PyFT8.txt', 'PyFT8', 'orange')])

