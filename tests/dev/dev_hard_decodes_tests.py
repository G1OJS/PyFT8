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

def plot_nchecks(candidates):
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
        candidates_with_message = [c for c in candidates if c.msg]
        unique_messages = set()
        for c in candidates_with_message:
            print(c.f0_idx, c.msg, c.decode_path)
            easy_candidates_f0_idxs.append(c.f0_idx)
            unique_messages.add(c.msg)
        print(f"Found {len(candidates_with_message)} decodes, {len(list(unique_messages))} unique")
                
       # with open("easy_decodes.pkl","wb") as f:
       #     pickle.dump(easy_candidates_f0_idxs,f)
       # print("Saved easy candidates list")

def plot_cand(f0_idx):
    fig, axes = plt.subplots()
    im = axes.imshow(spectrum.pgrid_fine[:,f0_idx:f0_idx+3*8], origin="lower", aspect="auto", 
                    cmap="inferno", interpolation="none", norm=LogNorm() )
    im.norm.vmin = im.norm.vmax/100000
    plt.show()

def ondecode(c):
    print(c.f0_idx, ','.join([h['step'] for h in c.decode_history]))

def new_search(f0_idx,fn_idx):
    print("Looking for further decodes")

    df = spectrum.df
    candidates = spectrum.search([f0_idx*df,fn_idx*df],"000000_000000")
    candidates = [c for c in candidates if not c.f0_idx in easy_candidates_f0_idxs]
    for c in candidates:
        c.demap(spectrum)

    for c in candidates:    
        for j in range(55):
            if(not c.decode_completed):
                c.progress_decode()

        print(c.f0_idx, c.decode_path)

    #plot_nchecks(candidates)

load_spectrum()

get_easy_candidate_f0_idxs()
#plot_spectrum()
#plot_cand(135)

new_search(135,136)
