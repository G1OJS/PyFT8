import matplotlib.pyplot as plt
import pandas as pd

def A():
    with open ("live_compare.csv","r") as f:
        lines = f.readlines()

    fix,ax = plt.subplots()

    n_its, nc = [],[]
    for l in lines:
        decoded = l.find("L00")
        if(decoded>0):
            n_its.append(len([c for c in l[76:decoded] if c == "L"]))
            nc.append(int(l[76:78]))

    ax.hist(n_its, bins = range(25))
    ax.set_xlabel("Number of iterations")
    ax.set_ylabel("Number of decodes")


def nchecks():
    w,p = [],[]
    with open("decodes.csv", "r") as f:
        for l in f.readlines():
            n,d = l.split(",")
            w.append(int(n))
            if('True' in d):
                p.append(int(n))
    fig,ax = plt.subplots()
    ax.hist(w, bins = range(50), label = "WSJTX",
            cumulative=-1, density = True, color = 'purple', alpha = 0.8)
    ax.hist(p, bins = range(50), label = "PyFT8",
            cumulative=-1, density = True, color = 'green', alpha = 0.8)
    ax.set_xlabel("Initial ncheck")
    ax.set_ylabel("Fraction of decodes (cumulative)")
    ax.legend()


nchecks()
plt.tight_layout()
plt.show()
