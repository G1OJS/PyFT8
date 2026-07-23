import threading
import numpy as np
import pyaudio

from PyFT8.time_utils import time_utils
from PyFT8.databases import call_hashes, add_call_hashes
from PyFT8.osd import osd_decode_minimal

WATERFALL_DOWNSAMPLE = 2
DEBUG_PRINTS = True
T_CYC = 15
N_SYMS = 79
SYM_RATE = 6.25
SAMP_RATE = 12000
COSTAS = [3,1,4,0,6,5,2]
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))
COSTAS_SYMB_IDXS = list(range(7)) + list(range(36,43)) + list(range(72,79))

#=========== Unpacking functions ========================================
def get_bitfields(bits, lengths):
    fields = []
    for n in lengths:
        mask = (1 << n) - 1
        fields.append(bits & mask)
        bits >>= n
    return *fields, bits

def unpack(bits):
    if not bits:
        return None
    
    i3, bits74 = get_bitfields(bits,[3])
    if i3 == 0:
        n3, bits71 = get_bitfields(bits74,[3])
        if n3 <= 4:
            return (['Free text', 'DXpedition','Field Day', 'Field Day', 'Telemetry'][n3],'not','implemented')
        else:
            return ('Unknown mode','not','implemented')
    elif i3 == 1 or i3 == 2: # 1 = Std Msg incl /R 2 = 'EU VHF' = Std Msg incl /P
        return unpack_std(bits74, i3)
    elif i3 == 3:
        return ('RTTY RU','not','implemented')
    elif i3 == 4:
        cq, rrr, swp, c58, hsh, _ = get_bitfields(bits74, [1,2,1,58,12]) 
        ca = "CQ" if cq else call_hashes.get((hsh,12), '<....>')
        cb = ""
        for i in range(12):
            cb = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"[c58 % 38] + cb
            c58 = c58 // 38
        cb =  cb.strip()
        add_call_hashes(cb)
        (ca, cb) = (cb, ca) if swp else (ca, cb)
        return (ca, cb, ('', 'RRR', 'RR73', '73')[rrr])
    elif i3 == 5:
        return ('EU VHF','not','implemented')

def unpack_std(bits74, i3):
    g16, cb29, ca29, _ = get_bitfields(bits74,[16,29,29])
    g15 = g16 & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        grid_rpt =  chr(65+a) + chr(65+b) + str(c) + str(d)
    elif g15 - 32400 <= 4:
        grid_rpt =  ('', '', 'RRR', 'RR73', '73')[g15 - 32400]
    else:
        prefix = 'R' if (g16 >> 15) else ''
        grid_rpt = prefix + f"{(g15 - 32435):+03d}"
    msg_tuple = (call_29(ca29, i3), call_29(cb29, i3), grid_rpt)
    if msg_tuple != ('','','') and msg_tuple is not None:
        return msg_tuple

def call_29(call_int29, i3):    
    portable_rover = call_int29 & 1
    call_int28 = call_int29>>1
    if call_int28 < 3:
        return ['DE', 'QRZ', 'CQ'][call_int28]
    elif call_int28 < 1004:
        return f"CQ {call_int28 - 3:03d}"
    elif call_int28 < 21443:
        x, txt = call_int28 - 1003, ''
        for i in range(4):
            txt = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"[int(x % 27)] + txt
            x //= 27
        return f"CQ {txt.strip()}"
    elif call_int28 < 2063592+4194303:
        return call_hashes.get((call_int28 - 2063592, 22), '<....>')
    else:
        call = standard_call28(call_int28, i3)
        if portable_rover:
            call = call + ('/P' if i3 == 2 else '/R')
        add_call_hashes(call)
        return call

def standard_call28(call_int28, i3):
    nn = call_int28 - (2063592 + 4194304)
    from string import ascii_uppercase as ltrs, digits as digs
    call_fields = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                    (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
    chars = []
    for alphabet, div in call_fields:
        idx, nn = divmod(nn, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    return call

#============== CRC ===========================================================
def check_crc(bits91_int):
    bits77_int = bits91_int >> 14
    if(bits77_int > 0):
        crc14_int = 0
        for i in range(96):
            inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
            bit14 = (crc14_int >> (14 - 1)) & 1
            crc14_int = ((crc14_int << 1) & ((1 << 14) - 1)) | inbit
            if bit14:
                crc14_int ^= 0x2757
        if(crc14_int == bits91_int & 0b11111111111111):
            return bits77_int

#============== LDPC ===========================================================
CV6idx = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
CV7idx = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)

import warnings
warnings.filterwarnings("error")

def pass_ldpc_messages(llr, CVidx, mC2V_prev, update_collector):
    mV2C = llr[CVidx] - mC2V_prev
    tanh_mV2C = np.tanh(-mV2C)
    tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
    orig_err = np.geterr()
    np.seterr(all = 'ignore')
    tanh_mC2V = np.divide(tanh_mC2V, tanh_mV2C)
    np.seterr(**orig_err)
    alpha_atanh_approx = 1.18
    mC2V_curr  = tanh_mC2V / ((tanh_mC2V - alpha_atanh_approx) * (alpha_atanh_approx + tanh_mC2V))
    np.add.at(update_collector, CVidx, mC2V_curr - mC2V_prev)
    return mC2V_curr

def ldpc_decode(llr, max_ncheck0, max_iters):
    mC2V_prev6, mC2V_prev7 = np.zeros(CV6idx.shape, dtype=np.float32), np.zeros(CV7idx.shape, dtype=np.float32)
    for n_its in range(max_iters):
        bits6, bits7 = llr[CV6idx] > 0, llr[CV7idx] > 0
        parity6, parity7 = np.sum(bits6, axis=1) & 1, np.sum(bits7, axis=1) & 1
        ncheck = int(np.sum(parity7) + np.sum(parity6))
        if n_its == 0 and ncheck > max_ncheck0:
            return None, -1, []
        if ncheck == 0:
            bits91_int = 0
            for bit in (llr[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            msg_tuple = unpack(bits77_int)
            if msg_tuple:
                return msg_tuple, n_its, []
        else:
            update_collector = np.zeros_like(llr)
            mC2V_prev6 = pass_ldpc_messages(llr, CV6idx, mC2V_prev6, update_collector)
            mC2V_prev7 = pass_ldpc_messages(llr, CV7idx, mC2V_prev7, update_collector)
            llr += update_collector

    return None, -1, llr

#============== AUDIO IN ===========================================================
class AudioIn:
    def __init__(self, search_freq_range, input_device_keywords):
        self.input_device_idx = None
        self.search_hps, self.search_bpt = 4, 2
        self.search_freq_range = search_freq_range
        self.search_fft_len = int(self.search_bpt * SAMP_RATE // SYM_RATE)
        self.df = SYM_RATE / self.search_bpt
        self.search_f0_idx_range = [int(self.search_freq_range[0] / self.df),
                                    int((self.search_freq_range[1]) / self.df)]
        self.search_fft_window = np.hanning(self.search_fft_len).astype(np.float32)
        self.search_hops_per_cycle = int(T_CYC * SYM_RATE * self.search_hps)
        self.search_hops_per_grid = 2*self.search_hops_per_cycle
        self.dt = T_CYC / self.search_hops_per_cycle
        self.search_grid = np.ones((self.search_hops_per_grid, self.search_f0_idx_range[1]  + 8 * self.search_bpt ), dtype = np.float32)
        self.samples_perhop = int(SAMP_RATE / (SYM_RATE * self.search_hps))
        self.samples_per_cycle = int(SAMP_RATE * T_CYC)

        self.cycle_audio_buffer_ptr, self.search_grid_ptr = 0, 0
        self.waterfall_data = self._set_waterfall_data()
        self.search_audio_buffer = np.zeros(self.search_fft_len, dtype=np.float32)
        self.search_fft_in = np.zeros(self.search_fft_len, dtype=np.float32)        
        self.cycle_audio_buffer = np.zeros(192000, dtype=np.float32)
        self.adj, self.cycle_audio_buffer_ptr_prev, self.t_prev = 1.0, -1, None
        self._set_pointers()
        self._find_input_device(input_device_keywords)

        threading.Thread(target = self._load_streamed_audio, daemon=True).start()
        threading.Thread(target = self._manage_audio_in_cycle, daemon=True).start()

    def _find_input_device(self, input_device_keywords):
        pya = pyaudio.PyAudio()
        for dev_idx in range(pya.get_device_count()):
            name = pya.get_device_info_by_index(dev_idx)['name']
            match = True
            for pattern in input_device_keywords.replace(' ','').split(','):
                if (not pattern in name): match = False
            if(match):
                self.input_device_idx = dev_idx
                time_utils.tlog(f"[Audio] using input audio device {dev_idx} {name})", verbose = True)
                break

    def _load_streamed_audio(self):
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = SAMP_RATE, input = True, input_device_index = self.input_device_idx,
            frames_per_buffer = self.samples_perhop, stream_callback=self._callback,)
        self._set_pointers()
        self.stream.start_stream()
            
    def _set_waterfall_data(self):
        downsample = WATERFALL_DOWNSAMPLE
        data = self.search_grid[::downsample,::downsample].T
        df, dt = self.df * downsample, self.dt * downsample
        sig_w, sig_h = int(79*self.search_hps/downsample), int(8*self.search_bpt/downsample)
        pixels_per_cycle = int(self.search_hops_per_cycle / downsample)
        return {'data':data, 'df':df, 'dt':dt, 'sig_w':sig_w, 'sig_h':sig_h, 'pixels_per_cycle':pixels_per_cycle}

    def _manage_audio_in_cycle(self):
        cycle_adj = 0
        search_grid_ptr_prev = 0
        while True:
            time_utils.sleep(0.04)
            self.odd_even = int(self.search_grid_ptr / self.search_hops_per_cycle)
            self.cycle_h0 = int(self.odd_even * self.search_hops_per_cycle)
            if self.search_grid_ptr % (self.search_hops_per_cycle - cycle_adj) < search_grid_ptr_prev:
                tcyc = time_utils.cycle_time()
                time_utils.tlog(f"[Receiver] Cycle rollover at {tcyc:7.3f}s", verbose = True)
                if tcyc > 0.25:
                    self._set_pointers() # could be merged into this func
            search_grid_ptr_prev = self.search_grid_ptr % (self.search_hops_per_cycle - cycle_adj)

    def _set_pointers(self, adj_tolerance = 0.25):
        t = time_utils.time()
        search_grid_ptr = int(self.search_hops_per_grid * (t % (2 * T_CYC)) / (2 * T_CYC))
        cycle_audio_buffer_ptr = int(SAMP_RATE * (t % T_CYC))
        deltasamps = cycle_audio_buffer_ptr - self.cycle_audio_buffer_ptr
        deltahops = search_grid_ptr - self.search_grid_ptr
        deltasecs = deltasamps / SAMP_RATE
        if np.abs(deltasecs) > adj_tolerance:
            self.cycle_audio_buffer_ptr = cycle_audio_buffer_ptr
            self.search_grid_ptr = search_grid_ptr
        time_utils.tlog(f"[Audio] Grid pointers adjusted (t={deltasecs:6.2f}s, h={deltahops}, s={deltasamps})", verbose = DEBUG_PRINTS)
        
    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16)#.astype(np.float32)
        ns = self.samples_perhop
        self.search_audio_buffer[:-ns] = self.search_audio_buffer[ns:]
        self.search_audio_buffer[-ns:] = samples
        np.multiply(self.search_audio_buffer, self.search_fft_window, out = self.search_fft_in)
        z = np.fft.rfft(self.search_fft_in)[:self.search_grid.shape[1]]
        
        self.search_grid[self.search_grid_ptr, :] = 20*np.log10(np.abs(z))
        self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid

        self.cycle_audio_buffer[self.cycle_audio_buffer_ptr:self.cycle_audio_buffer_ptr + ns] = samples
        self.cycle_audio_buffer_ptr = (self.cycle_audio_buffer_ptr + ns) % self.samples_per_cycle
        return (None, pyaudio.paContinue)


#============== CANDIDATE ===========================================================

ap_patterns = [
                ['None',    0,  []                                                                  ],                                                                # no AP
                ['CQ',      0,  [0,0,0,0,0 ,0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,1,0,0]    ],
                ['RR73',    58, [0,1, 1,1,1,1,1, 0,0,1,1,1, 0,1,0,1,0, 0,1]                         ],
                ['73',      58, [0,1, 1,1,1,1,1, 0,1,0,0,1, 0,1,0,0,0, 0,1]                         ],
                ['RRR',     58, [0,1, 1,1,1,1,1, 0,1,0,0,1, 0,0,1,0,0, 0,1]                         ],
              ]

class Candidate:
    def __init__(self, origin, search_grid_bounds, llr_sd_min = 5):
        self.origin = origin
        self.search_grid_bounds = search_grid_bounds
        self.decoded_from_grid = True
        self.demap_started, self.decode_completed = False, False
        self.n_sync_matches = -1
        self.fast_decode_tried = False
        self.msg_tuple = None
        self.saved_llrs = []
        self.ipass = 0
        self.llr_sd_min = llr_sd_min
        self.llr_sd, self.ipass, self.n_its, self.snr = 0, 0, 0, -30
        csync = np.full((7, 7), -1/6, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            csync[sym_idx, tone] = 1.0
        self.csync_7x7 =  csync.ravel()
        self.fft2_len = 3200
        self.spectrum = np.zeros(self.fft2_len, dtype = np.complex64)
        self.cgrid = np.ones((N_SYMS, 8), dtype = np.complex64)

    def package(self):
        o = self.origin
        decode_status = self.decode_status
        tsec, fHz = o['tsec'], o['fHz']
        their_snr = f"{self.snr:+03d}"
        msg_text = ' '.join(self.msg_tuple)
        all_txt_format = f"{o['cyclestart_string']} {their_snr} {(tsec-0.5):4.1f} {fHz:4.0f} ~ {msg_text}"
        return {"band":o['band'], "tsec":tsec, "fHz":fHz, "msg_tuple":self.msg_tuple, "their_snr": their_snr, "their_tx_cycle":o['odd_even'],
                "decode_completed": time_utils.time(), "all_txt_format": all_txt_format, 'decode_status':decode_status}
        
    def get_tfgrid(self, all_audio_spectrum, fb_0, fb_bot, fb_top, tb_0): 
        fft1_len = len(all_audio_spectrum)

        # downsample to 32 samples per symbol / 200 samples per sec
        self.spectrum[:(fb_top - fb_0)] = all_audio_spectrum[fb_0:fb_top]
        self.spectrum[-(fb_0-fb_bot):] = all_audio_spectrum[fb_bot:fb_0]
        candidate_zsig = np.fft.ifft(self.spectrum)

        # get candidate symbol spectra x79 with df = 1 tone spacing
        symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
        idx = tb_0 + np.arange(N_SYMS)*32
        idx = np.clip(idx, 0, len(candidate_zsig)-32)
        symbols = np.empty((N_SYMS,32), dtype=np.complex64)
        for j, i0 in enumerate(idx):
            symbols[j,:] = candidate_zsig[i0:i0+32]
        self.cgrid = np.abs(np.fft.fft(symbols, axis=1)[:, :8])
        self.score = float(np.dot(self.cgrid[36:43, :7].ravel(), self.csync_7x7))

    def dB_to_llr(self, p):
        snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        mean = np.mean(llr)
        var = np.mean(llr*llr) - mean*mean
        rootvar = np.sqrt(var)
        return 2.83 * llr / rootvar, rootvar, snr

    def demap(self, all_audio_spectrum):
        self.decoded_from_grid = False
        df = SAMP_RATE / 192000
        fHz, tsec = self.origin['fHz'], self.origin['tsec']
        fb_0 = int(0.5 + fHz / df )
        fb_top = int(0.5 + (fHz + 8.5*SYM_RATE) / df )
        fb_bot = int(0.5 + (fHz - 1.5*SYM_RATE) / df )
        dt = 0.005
        tb_0 = int(tsec/dt)
        ftweak, ttweak = 0, 0

        ttweaks = range(-16, 0, 4) # 4 steps = 20ms = 1/8 sample, 1/4 sample = 8 steps
        scores = []
        for ttweak in ttweaks:
            self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ttweak = ttweaks[np.argmax(scores)]

        ftweaks = range(-50, 51, 16) # 16 steps = 1Hz, 6.25Hz = 100 steps
        scores = []
        for ftweak in ftweaks:
            self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ftweak = ftweaks[np.argmax(scores)]

        self.get_tfgrid(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)

        p = self.cgrid[COSTAS_SYMB_IDXS, :]
        ccheck = np.argmax(p, axis = 1) - (COSTAS * 3)
        self.n_sync_matches = len([c for c in ccheck if c == 0])
        if self.n_sync_matches <= 6:
            self.decode_completed = True
            return
        
        p = 20*np.log10(self.cgrid[PAYLOAD_SYMB_IDXS, :])
        self.llr, self.llr_sd, self.snr = self.dB_to_llr(p)
        self.origin.update({'tsec': float(self.origin['tsec'] + ttweak / 200),
                            'fHz':float(self.origin['fHz'] + ftweak / 16) })

    def fast_demap_decode(self, payload_on_search_grid):
        self.llr, self.llr_sd, self.snr = self.dB_to_llr(payload_on_search_grid)
        self._decode_ldpc_AP('grid', [1,0], 35, 5, False) # try CQ pattern first

    def decode(self, current_max_ipass):
        if self.ipass > current_max_ipass:
            return
        if self.llr_sd < self.llr_sd_min:
            self.decode_status = 'llr reject'
            self.decode_completed = True
            return
        if self.ipass == 0:
            self.decode_status = 'fine FLDPC'
            self._decode_ldpc_AP('fine', [0], 35, 5, False)
        if self.ipass == 1:
            self._decode_ldpc_AP('fine', [0,1,2,3,4], 55, 25, True)
        if self.ipass == 2:
            self.rel_ord = np.argsort(np.abs(self.llr))[::-1]
            self.decode_status = 'fine OSD'
            self._decode_osd(self.llr)
        i_saved = self.ipass - 3
        if len(self.saved_llrs) > i_saved >= 0:
            pat_name, llr = self.saved_llrs[i_saved]
            self.decode_status = f'fine OSD {pat_name}'
            self._decode_osd(llr)
        if self.msg_tuple or i_saved == len(self.saved_llrs):
            self.decode_completed = True
        self.ipass +=1
                
    def _decode_ldpc_AP(self, source, ap_indexes, max_nc0, max_its, save_llr):
        self.saved_llrs = []
        for ipat in ap_indexes:
            pat_name, b0, ap_pattern = ap_patterns[ipat]
            self.decode_status = f'{source} LDPC-AP {pat_name}'
            llr = self.llr.copy()
            if ipat > 0:
                for b, bval in enumerate(ap_pattern):
                    llr[b0 + b] = (bval*2-1) * 5
                if ipat == 1:
                    llr[74:76] = -5
                    llr[76] = 5
            self.msg_tuple, self.n_its, output_llr = ldpc_decode(llr, max_nc0, max_its)
            if self.msg_tuple:
                break
            else:
                if save_llr and len(output_llr) == 174:
                    self.saved_llrs.append((pat_name, output_llr))
                
    def _decode_osd(self, llr):
            cw = osd_decode_minimal(llr, self.rel_ord)
            bits91_int = 0
            for bit in (cw[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            msg_tuple = unpack(bits77_int)
            if msg_tuple:
                self.msg_tuple, self.n_its = msg_tuple, -1

#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, input_device_keywords, process_message, sync_score_min = 100, max_cands = 1000,
                 search_freq_range = [100, 3000], search_timerange = [-2, 5], verbose = False):
        self.audio_in = AudioIn(search_freq_range, input_device_keywords)
        self.process_message = process_message
        self.sync_score_min, self.max_cands = sync_score_min, max_cands
        self.candidates = []
        self.verbose = verbose
        self.search_h0_range = [int((t+0.5)*self.audio_in.search_hps*SYM_RATE) for t in search_timerange]
        self.search_start_hop = self.search_h0_range[1] + 43 * self.audio_in.search_hps
        dt = 1.0 / (SYM_RATE * self.audio_in.search_hps)
        self.base_search_hops = 36 * self.audio_in.search_hps + np.arange(7) * self.audio_in.search_hps 
        csync = np.full((7, 7 * self.audio_in.search_bpt), -1/6, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            fbins = range(tone * self.audio_in.search_bpt, (tone+1) * self.audio_in.search_bpt)
            csync[sym_idx, fbins] = 1.0
        self.csync_search = csync.ravel()
        self.band = None
        
        time_utils.set_cycle_length(T_CYC)
        time_utils.tlog(f"[Receiver] Search hops {self.search_h0_range[0]:3d} to {self.search_h0_range[1]:3d}", verbose = self.verbose)
        time_utils.tlog(f"[Receiver] Start search at hop {self.search_start_hop:3d}", verbose = self.verbose)
        
        time_utils.sleep(0.5)
        threading.Thread(target=self.manage_cycle, daemon=True).start()
        
    def search(self, cyclestart_string, odd_even, cycle_h0):
        cands = []
        hops_per_sig = self.audio_in.search_hps * PAYLOAD_SYMB_IDXS[-1]
        for f0_idx in range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1], 2):
            p = self.audio_in.search_grid[:, f0_idx: f0_idx + 7*self.audio_in.search_bpt]
            origin = {'score':0}
            for h0_idx in range(self.search_h0_range[0], self.search_h0_range[1]):
                score = float(np.dot(p[h0_idx + cycle_h0 + self.base_search_hops + self.audio_in.search_hps, :].ravel(), self.csync_search))
                test_sync = {'h0_idx':h0_idx,  'f0_idx':f0_idx,
                             'tsec':h0_idx/(self.audio_in.search_hps * SYM_RATE),
                             'fHz':SYM_RATE * f0_idx / self.audio_in.search_bpt, 'score':score}
                if test_sync['score'] > origin['score']:
                    origin = test_sync
            if origin['score'] > self.sync_score_min:
                h0, tsec = origin['h0_idx'], origin['tsec']
                origin.update({'cyclestart_string':cyclestart_string, 'band':self.band, 'odd_even':odd_even})
                search_grid_h0 = cycle_h0 + h0 + self.audio_in.search_hps
                search_grid_hn = cycle_h0 + h0 + self.audio_in.search_hps + hops_per_sig
                c = Candidate(origin, [search_grid_h0, search_grid_hn])
                cands.append(c)
        cands.sort(key = lambda c: c.origin['score'], reverse = True)
        self.candidates = cands[:self.max_cands]

    def set_band(self, band):
        self.band = band

    def manage_cycle(self):
        dashes = "======================================================"
        duplicate_filter = set()
        time_utils.tlog(f"[Receiver] running", verbose = self.verbose)
        last_spectrum_calc = -1
        search_grid_ptr_prev = 0
        cycle_searched = False
        end_decoding_message_printed = False
        while True:
            time_utils.sleep(0.1)
            if self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle < search_grid_ptr_prev:
                cycle_searched = False
            search_grid_ptr_prev = self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle

            to_decode = []
            for c in self.candidates:

                if not c.fast_decode_tried:
                    if not (c.search_grid_bounds[0] <= self.audio_in.search_grid_ptr <= c.search_grid_bounds[1]):
                        hops = np.array([(c.search_grid_bounds[0] + self.audio_in.search_hps * s)% self.audio_in.search_hops_per_grid for s in PAYLOAD_SYMB_IDXS])
                        freqs = np.array([c.origin['f0_idx'] + self.audio_in.search_bpt//2 + t * self.audio_in.search_bpt for t in range(8)])
                        tfgrid_payload_dB = self.audio_in.search_grid[hops,:][:, freqs]
                        c.fast_demap_decode(tfgrid_payload_dB)
                        c.fast_decode_tried = True

                if not c.decode_completed and not c.demap_started:
                    if not (c.search_grid_bounds[0] <= self.audio_in.search_grid_ptr <= c.search_grid_bounds[1]):
                        if self.audio_in.search_grid_ptr - last_spectrum_calc > 0 : # only calc full spectrum if more samples received
                            all_audio_spectrum = np.fft.rfft(self.audio_in.cycle_audio_buffer)
                        last_spectrum_calc = self.audio_in.search_grid_ptr
                        c.demap(all_audio_spectrum)
                        c.demap_started = True
                        
                if not c.decode_completed and c.llr_sd > 0:  
                    to_decode.append(c)

                if c.msg_tuple:
                    c.decode_completed = True
                    key = c.origin['cyclestart_string'] + ''.join(c.msg_tuple)
                    if (key not in duplicate_filter):
                        duplicate_filter.add(key)
                        m = c.package()
                        self.process_message(m)
                
            if len(to_decode):
                to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
                max_ipass = 1 + np.min([c.ipass for c in to_decode])
                for c in to_decode[:40]:
                    c.decode(max_ipass)
            else:
                if not end_decoding_message_printed and len([c for c in self.candidates if c.demap_started]):
                    h = self.audio_in.search_grid_ptr
                    t = h / (SYM_RATE * self.audio_in.search_hps)
                    time_utils.tlog(f"[Receiver] Finished decoding at t={t:6.2f}s", verbose = True)
                    end_decoding_message_printed = True

            if not cycle_searched and self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle > self.search_start_hop:
                hstart = self.audio_in.search_grid_ptr
                tstart = hstart / (SYM_RATE * self.audio_in.search_hps)
                time_utils.tlog(f"[Cycle manager] start search at hop {hstart} ({tstart:6.2f}s)", verbose = True)
                cyclestart_string = time_utils.cyclestart_string(time_utils.time())
                timeouts = [c for c in self.candidates if not c.decode_completed]
                if len(timeouts):
                    ipasses = [c.ipass for c in timeouts]
                    time_utils.tlog(f"[Receiver] Warning - {len(timeouts)} candidates ran out of decoding time, ipass = {ipasses}", verbose = True)
                self.search(cyclestart_string, self.audio_in.odd_even, self.audio_in.cycle_h0)
                cycle_searched = True
                end_decoding_message_printed = False
                hstop = self.audio_in.search_grid_ptr
                tsearch = (hstop-hstart)/ (SYM_RATE * self.audio_in.search_hps)
                time_utils.tlog(f"[Cycle manager] New spectrum searched in {tsearch}s -> {len(self.candidates)} candidates", verbose = True) 

