import matplotlib.pyplot as plt
import pandas as pd
import pickle as pkl
from matplotlib.colors import LogNorm
from PyFT8.cycle_manager import Spectrum, Candidate
from PyFT8.sigspecs import FT8
from PyFT8.audio import AudioIn


def load_spectrum():
    global spectrum
    with open("pgrid.pkl", "rb") as f:
        pgrid = pkl.load(f)

    audio_in = AudioIn(12000, FT8.symbols_persec,
                       3500, 3, 3, on_fft = None)
      
    spectrum = Spectrum(FT8, 12000, audio_in.nFreqs, 3500, 3, 3)
    spectrum.pgrid_fine = pgrid

def plot_spectrum():
    fig, axes = plt.subplots()
    im = axes.imshow(spectrum.pgrid_fine, origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", norm=LogNorm() )
    im.norm.vmin = im.norm.vmax/100000
    plt.show()

def plot_nchecks():
    fig, axes = plt.subplots()
    p = [c.ncheck0 for c in candidates]
    axes.hist(p, bins = range(60),
            cumulative = 0, alpha = 0.8, lw=0.5, edgecolor = "black")
    p = [c.ncheck for c in candidates]
    axes.hist(p, bins = range(60),
            cumulative = 0, color = 'green', alpha = 0.8, lw=0.5, edgecolor = "black")
    plt.show()

easy_candidates_f0_idxs =[]
def ondecode_easy(c):
    global easy_candidates_f0_idxs
    print(c.f0_idx, c.fHz, c.msg)
    easy_candidates_f0_idxs.append(c.f0_idx)

def get_easy_candidate_f0_idxs():
    global spectrum, easy_candidates_f0_idxs
    import pickle, os
    if(os.path.exists("easy_decodes.pkl")):
        with open ("easy_decodes.pkl","rb") as f:
            easy_candidates_f0_idxs = pickle.load(f)
        print("Loaded easy candidates list")
    else:
        print("Finding easy candidates for current demapper & decoder")
        candidates = spectrum.search([200,3000],"000000_000000")
        for c in candidates:
            c.demap(spectrum)
            for j in range(55):
                if(not c.decode_completed):
                    c.progress_decode()
                else:
                    if(not c.decode_verified):
                        dupes=set() # re-initialise to stop dedupe
                        c.verify_decode(dupes, ondecode_easy)
        with open("easy_decodes.pkl","wb") as f:
            pickle.dump(easy_candidates_f0_idxs,f)
        print("Saved easy candidates list")

load_spectrum()
#plot_spectrum()
get_easy_candidate_f0_idxs()


def ondecode(c):
    print(c.msg)

print("Looking for further decodes")
dupes=set()
candidates = spectrum.search([200,3000],"000000_000000")
candidates = [c for c in candidates if not c.f0_idx in easy_candidates_f0_idxs]
for c in candidates:
    c.demap(spectrum)

for c in candidates:    
    for j in range(55):
        if(not c.decode_completed):
            c.progress_decode()
        else:
            if(not c.decode_verified):
                c.verify_decode(dupes, ondecode)

plot_nchecks()

