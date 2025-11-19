import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import math
import numpy as np

from PyFT8.rx.FT8_demodulator import Spectrum, Candidate
from PyFT8.signaldefs import FT8
import PyFT8.FT8_crc as crc
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.rx.waterfall import Waterfall
from PyFT8.comms_hub import config

eps = 1e-12
        
class FT8Demodulator:
    def __init__(self):
        sample_rate=12000
        fbins_pertone=3
        hops_persymb=5
        sigspec=FT8
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec
        self.spectrum = Spectrum( fbins_pertone=self.fbins_pertone, hops_persymb=self.hops_persymb,
                                  sample_rate=self.sample_rate, sigspec=self.sigspec)
        self.candidate_size = (self.sigspec.num_symbols * self.hops_persymb,
                               self.sigspec.tones_persymb * self.fbins_pertone)
        # ---- Costas sync mask ---- nsym(7) x nfBins(7 * self.fbins_pertone)
        nsym = self.sigspec.costas_len
        self._csync = np.full((nsym, self.candidate_size[1]), -1/(nsym-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* self.fbins_pertone, (tone+1) * self.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, 7*self.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(nsym) * self.spectrum.hops_persymb
     
    def load_audio(self, audio_in):
        nSamps = len(audio_in)
        nHops_loaded = int(self.hops_persymb * self.sigspec.symbols_persec * (nSamps-self.spectrum.FFT_len)/self.sample_rate)
        fine_grid_complex = np.zeros((nHops_loaded, self.spectrum.nFreqs), dtype = np.complex64)
        self.samples_perhop = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb) )                                   
        for hop_idx in range(nHops_loaded):
            sample_idx = int(hop_idx * self.samples_perhop)
            aud = audio_in[sample_idx:sample_idx + self.spectrum.FFT_len] * np.kaiser(self.spectrum.FFT_len, 14)
            fine_grid_complex[hop_idx,:] = np.fft.rfft(aud)[:self.spectrum.nFreqs]
        self.spectrum.fill_arrays(fine_grid_complex)
        timers.timedLog(f"[load_audio] Loaded {nHops_loaded} hops ({nHops_loaded*0.16/self.hops_persymb:.2f}s)")
        
        
wav_file = "210703_133430.wav"
wav_file = "251115_135700.wav"

demod = FT8Demodulator()

timers.timedLog("Read wav")
audio_in = audio.read_wav_file(wav_file)
timers.timedLog("Load audio")
demod.load_audio(audio_in)

timers.timedLog("Start search")
matches = []
f0_idxs = range(demod.spectrum.nFreqs - demod.candidate_size[1])
for f0_idx in f0_idxs:
    c = Candidate(demod.spectrum, f0_idx, demod.candidate_size, "")
    fc = demod.spectrum.fine_grid_complex[:,f0_idx:f0_idx + c.size[1]]
    c.fine_grid_pwr = np.abs(fc)**2
    c.fine_grid_pwr = c.fine_grid_pwr / np.max(c.fine_grid_pwr)
    best = (0, f0_idx, -1e30)
    for h0 in range(demod.spectrum.hop0_window_size):
        window = c.fine_grid_pwr[h0 + demod.hop_idxs_Costas]
        test = (h0, f0_idx, np.sum(window * demod._csync))
        if test[2] > best[2]:
            best = test
    matches.append(best)
timers.timedLog("Finished search")


wf = Waterfall(demod.spectrum, f1=3500)
wf.update_main()
import matplotlib.patches as patches
matches.sort(key=lambda s: -s[2])
for m in matches[:50]:
    origin_img = (m[1]*demod.spectrum.df, m[0]*demod.spectrum.dt)
    rect = patches.Rectangle(origin_img, demod.sigspec.bw_Hz, 7*0.16,
      linewidth=1.2,edgecolor="lime", facecolor="none"
    )
    wf.ax_main.add_patch(rect)
    

#wf.ax_main.plot(np.arange(demod.spectrum.nFreqs - demod.candidate_size[1])*demod.spectrum.df, np.array(scores))
wf.fig.canvas.draw_idle()
wf.fig.canvas.flush_events()
wf.plt.pause(1)

