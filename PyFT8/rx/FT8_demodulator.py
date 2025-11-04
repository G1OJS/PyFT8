"""
wave file test
10:48:04.61 (=0.00) Start to Load audio from 210703_133430.wav
10:48:05.02 (+0.41) Start to Show spectrum
10:48:05.33 (+0.31) Start to Find candidates
10:48:05.42 (+0.09) Found 500 candidates
10:48:05.49 (+0.08) Start to deduplicate candidate frequencies
10:48:05.52 (+0.03) Now have 40 candidates
10:48:05.53 (+0.01) Start to sync candidates
10:48:05.63 (+0.10) Synced 30 candidates
10:48:05.66 (+0.02) Start to Show candidates
10:48:05.99 (+0.33) Start to demodulate candidates
10:48:06.98 (+0.99) Decodes: 6
Test     0.000 Rx FT8    000 -0.3 2154 WM3PEN EA6VQ -09 4
Test     0.000 Rx FT8    000  0.0 2569 W1FC F5BZB -08 10
Test     0.000 Rx FT8    000 -0.1  721 A92EE F5PSR -14 8
Test     0.000 Rx FT8    000  0.1  588 K1JT HA0DU KN07 11
Test     0.000 Rx FT8    000  0.0  638 N1JFU EA6EE -07 10
Test     0.000 Rx FT8    000 -0.1 1646 K1JT EA3AGB -15 7
"""

import math
import numpy as np

from PyFT8.datagrids import Spectrum, Bounds, Candidate
from PyFT8.signaldefs import FT8
from PyFT8.rx.decode174_91 import decode174_91
import PyFT8.FT8_crc as crc
import PyFT8.timers as timers
from PyFT8.comms_hub import config

global audio_in
audio_in = None

def log_decode(decode):
    timers.timedLog("No callback specified, logging: {decode}", logfile = "default_decodes.log", silent = True)

def cyclic_demodulator(onDecode = log_decode, onRxFreqDecode = log_decode):
    from PyFT8.comms_hub import config
    import threading
    import PyFT8.timers as timers
    import PyFT8.audio as audio
    MAX_START_OFFSET_SECONDS = 0.5
    END_RECORD_GAP_SECONDS = 1

    global audio_in
    while True:
        t_elapsed, t_remain, = timers.time_in_cycle()
        timers.sleep(t_remain)
        if(t_elapsed <5 and t_elapsed > MAX_START_OFFSET_SECONDS):
            timers.timedLog(f"Arrived to start recording at {t_elapsed} into cycle, waiting for next", silent = True)
        timers.timedLog("Cyclic demodulator requesting audio", silent = True)
        audio_in = audio.read_from_soundcard(timers.CYCLE_LENGTH - END_RECORD_GAP_SECONDS)
        threading.Thread(target=get_decodes, kwargs=({'onDecode':onDecode, 'onRxFreqDecode':onRxFreqDecode})).start()
        timers.timedLog("Cyclic demodulator passed audio for demodulating", silent = True)

def get_decodes(onDecode, onRxFreqDecode):
    from PyFT8.comms_hub import config
    import PyFT8.timers as timers
    from PyFT8.rx.waterfall import Waterfall

    demod = FT8Demodulator(sample_rate=12000, fbins_pertone=3, hops_persymb=3)
    cyclestart_str = timers.cyclestart_str(1)
    demod.spectrum.load_audio(audio_in)

    rx_freq_decode = demod.demod_rxFreq(cyclestart_str)
    onRxFreqDecode(rx_freq_decode)
    
    candidates = demod.find_candidates(0,3500)
    candidates = demod.deduplicate_candidate_freqs(candidates)
    for c in candidates:
        if(c.bounds.f0 == config.rxfreq): # don't repeat decode the Rx freq
            continue
        msg_payload = None
        demod.sync_candidate(c)
        decode = demod.demodulate_candidate(c, cyclestart_str)
        onDecode(decode)
  
class FT8Demodulator:
    def __init__(self, sample_rate=12000, fbins_pertone=3, hops_persymb=3, sigspec=FT8):
        # ft8c.f90 uses 4 hops per symbol and 2.5Hz fbins (2.5 bins per tone)
        self.sample_rate = sample_rate
        self.fbins_pertone = fbins_pertone
        self.hops_persymb = hops_persymb
        self.sigspec = sigspec
        self.max_t0_idx = int(self.hops_persymb * 2.0 *6.25)
        # ---- spectrum setup ----
        self.spectrum = Spectrum( fbins_pertone=self.fbins_pertone, hops_persymb=self.hops_persymb,
                                  sample_rate=self.sample_rate, sigspec=self.sigspec)
        # ---- FFT params ----
        self.FFT_size = self.spectrum.FFT_size
        self._hop_size = int(self.sample_rate / (self.sigspec.symbols_persec * self.hops_persymb)) 
        # ---- Costas sync mask ----
        h, w = self.sigspec.costas_len * self.hops_persymb, self.sigspec.tones_persymb * self.fbins_pertone
        self._csync = np.full((h, w), -1/7, np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            t0 = sym_idx * self.hops_persymb
            f0 = tone * self.fbins_pertone
            self._csync[t0:t0+self.hops_persymb, f0:f0+self.fbins_pertone] = 1.0
               
    # ======================================================
    # Candidate search and sync
    # ======================================================

    def find_candidates(self, f0, f1, topN=500):
        region = Bounds.from_physical(self.spectrum, 0, 15, f0, f1)
        candidates = []
        for f0_idx in region.f_idx_range:
            score = np.sum(self.spectrum.power[: , f0_idx:f0_idx+self._csync.shape[1]])
            candidates.append(Candidate(self.sigspec, self.spectrum, 0, f0_idx, score))
        candidates.sort(key=lambda c: -c.score)
        self.make_occupancy_array(candidates)
        return candidates[:topN]

    def deduplicate_candidate_freqs(self, candidates):
        min_sep_fbins = 0.5 * self.sigspec.tones_persymb * self.fbins_pertone
        deduplicated = []
        for c in candidates:
            keep_c = True
            for i, existing in enumerate(deduplicated):
                if abs(c.bounds.f0_idx - existing.bounds.f0_idx) < min_sep_fbins:
                    if c.score > existing.score * 1.3:  # >~1.1–1.3× stronger
                        deduplicated[i] = c
                    keep_c = False
                    break
            if keep_c:
                deduplicated.append(c)
        return deduplicated
    
    def sync_candidate(self, c):
        c.score = -1e10
        for t0_idx in range(self.spectrum.nHops - self.sigspec.num_symbols*self.hops_persymb-1):
            score = self._csync_score_3(t0_idx, c.bounds.f0_idx)
            if(score > c.score):
                c.score = score
                c.update_t0_idx(t0_idx)

    def _csync_score_3(self, t0_idx, f0_idx):
        score = 0.0
        fn_idx = f0_idx + self._csync.shape[1]
        nt = self._csync.shape[0]
        block_hopstarts = [0, 36 * self.hops_persymb, 72 * self.hops_persymb]
        for block_idx in block_hopstarts: 
            t_idx = t0_idx + block_idx
            pgrid = self.spectrum.power[t_idx:t_idx + nt, f0_idx:fn_idx]
            block_score = np.sum(pgrid * self._csync)
            if block_score > score: score = block_score 
        return score 

    # ======================================================
    # Low resource spectrum usage visualisation
    # ======================================================
    
    def make_occupancy_array(self, candidates, f0=0, f1=3500, bin_hz=10):
        from PyFT8.comms_hub import send_to_ui_ws
        bins = np.arange(f0, f1 + bin_hz, bin_hz)
        for c in candidates:
            bins[int((c.bounds.f0-f0)/bin_hz)] += c.score
        bins = bins/np.max(bins)
        bins = 10*np.log10(bins + 1e-12)
        bins = 1 + np.clip(bins, -40, 0) / 40
        # find good clear frequency
        fs0, fs1 = 1000,1500
        bin0 = int((fs0-f0)/bin_hz)
        bin1 = int((fs1-f0)/bin_hz)
        clear_freq = fs0 + bin_hz*np.argmin(bins[bin0:bin1])
        # send occupancy and clear freq to UI
        config.update_clearest_txfreq(clear_freq)
        send_to_ui_ws("freq_occ_array", {'histogram':bins.tolist()})
        
    # ======================================================
    # Demodulation
    # ======================================================

    def demod_rxFreq(self, cyclestart_str):
        f0_idx = int(np.searchsorted(self.spectrum.freqs, config.rxfreq))
        candidate = Candidate(self.sigspec, self.spectrum, 0, f0_idx, -50)
        self.sync_candidate(candidate)
        timers.timedLog(f"Rx candidate synced {candidate.bounds.t0} {candidate.bounds.f0}", silent = True)
        decode = self.demodulate_candidate(candidate, cyclestart_str = cyclestart_str)
        return decode

    def demodulate_candidate(self, candidate, cyclestart_str):
        c = candidate
        LLR174s=[]
        pgrid = c.power_grid
        gray_mask = self.sigspec.gray_mask
        for symb_idx in c.sigspec.payload_symb_idxs:
            sigma2 = self.spectrum.noise_per_symb[symb_idx]
            tone_powers_scaled = pgrid[symb_idx, :] / sigma2
            m1 = np.where(gray_mask, tone_powers_scaled[:, None], -np.inf)
            m0 = np.where(~gray_mask, tone_powers_scaled[:, None], -np.inf)
            LLR_sym = np.logaddexp.reduce(m1, axis=0) - np.logaddexp.reduce(m0, axis=0)
            LLR174s.extend(LLR_sym)
        ncheck, bits, n_its = decode174_91(LLR174s)
        if(ncheck == 0):
            c.demodulated_by = f"LLR-LDPC ({n_its})"
            c.payload_bits = bits
            c.snr = -24 if c.score==0 else int(12*np.log10(c.score/1e9) - 31)
            c.snr = np.clip(c.snr, -24,24).item()
            decode = FT8_decode(c, cyclestart_str)
            if(decode): c.message = decode['decode_dict']['message'] 
            return decode
    
# ======================================================
# FT8 Unpacking functions
# ======================================================

def unpack_ft8_c28(c28):
    from string import ascii_uppercase as ltrs, digits as digs
    if c28<3: return ["DE", 'QRZ','CQ'][c28]
    n = c28 - 2_063_592 - 4_194_304 # NTOKENS, MAX22
    if n >= 0:
        charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
        divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
        indices = []
        for d in divisors:
            i, n = divmod(n, d)
            indices.append(i)
        callsign = ''.join(t[i] for t, i in zip(charmap, indices)).lstrip()
        return callsign.strip()
    return '<...>'

def unpack_ft8_g15(g15):
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    return f"{snr:+03d}"

def FT8_decode(signal, cyclestart_str):
    # need to add support for /P and R+report (R-05)
    bits = signal.payload_bits
    i3 = 4*bits[74]+2*bits[75]+bits[76]
    c28_a = int(''.join(str(b) for b in bits[0:28]), 2)
    c28_b = int(''.join(str(b) for b in bits[29:57]), 2)
    g15  = int(''.join(str(b) for b in bits[59:74]), 2)
    if(c28_a + c28_b + g15 == 0):
        return
    call_a = unpack_ft8_c28(c28_a)
    call_b =  unpack_ft8_c28(c28_b)
    grid_rpt = unpack_ft8_g15(g15)
    freq_str = f"{signal.bounds.f0:4.0f}"
    message = f"{call_a} {call_b} {grid_rpt}"
    all_txt_line = f"{cyclestart_str}     0.000 Rx FT8    {signal.snr:+03d} {signal.bounds.t0 :4.1f} {signal.bounds.f0 :4.0f} {message}"
    decode_dict = {'cyclestart_str':cyclestart_str , 'freq':freq_str, 'call_a':call_a,
                 'call_b':call_b, 'grid_rpt':grid_rpt, 't0_idx':signal.bounds.t0_idx,
                   'dt':f"{signal.bounds.t0 :4.1f}", 'snr':signal.snr, 'priority':False, 'message':message}
    return {'all_txt_line':all_txt_line, 'decode_dict':decode_dict}

