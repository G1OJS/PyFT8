import matplotlib.pyplot as plt
import pandas as pd
import pickle as pkl
from matplotlib.colors import LogNorm
from PyFT8.cycle_manager import Spectrum, Candidate
from PyFT8.sigspecs import FT8
from PyFT8.audio import AudioIn

with open("pgrid.pkl", "rb") as f:
    pgrid = pkl.load(f)

fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
cols = ['#1E88E5','#2E7D32','#6A1B9A','#90CAF9','#A5D6A7','#ebd2f3','red']


fig, axes = plt.subplots(2,1)
im = axes[0].imshow(pgrid, origin="lower", aspect="auto", 
                cmap="inferno", interpolation="none", norm=LogNorm() )
im.norm.vmin = im.norm.vmax/100000

audio_in = AudioIn(12000, FT8.symbols_persec,
                   3500, 3, 3, on_fft = None)
  
spectrum = Spectrum(FT8, 12000, audio_in.nFreqs, 3500, 3, 3)
spectrum.pgrid_fine = pgrid

def ondecode(c):
    print(c.msg)
    
axes[1].set_xlabel("ncheck")
axes[1].set_ylabel(f"Number")
axes[1].set_title(f"Ncheck after max 5 iterations")
plt.ion()

for i, param in enumerate([4.2]):
    dupes=set()
    candidates = spectrum.search([200,3000],"000000_000000")
    for c in candidates:
        c.demap(spectrum, param)
        for j in range(55):
            if(not c.decode_completed):
                c.progress_decode()
            else:
                if(not c.decode_verified):
                    c.verify_decode(dupes, ondecode)

    print(f"{len(dupes)} decodes")
    p = [c.ncheck for c in candidates]
    axes[1].hist(p, bins = range(60), label = ['raw','llr freeze'][i],
            cumulative = 0, color = cols[i], alpha = 0.8, lw=0.5, edgecolor = "black")
    axes[1].legend()
    plt.pause(.1)


