import numpy as np
import matplotlib.pyplot as plt
import time, pyaudio, threading, queue

params = {'MIN_LLR_SD': 0.0,'HPS': 4, 'BPT':2,'SYM_RATE': 6.25,'SAMP_RATE': 12000, 'T_CYC':15, 'WFBOX_LIFETIME': 25,
          'T_SEARCH_0': 4.6, 'T_SEARCH_1': 10.6, 'PAYLOAD_SYMBOLS': 79-7, 'LDPC_CONTROL': (45, 12) }
params.update({'H0_RANGE': [-7 * params['HPS'], int(3.48 * params['SYM_RATE'] * params['HPS'])]})

#=========== Unpacking functions ========================================
from string import ascii_uppercase as ltrs, digits as digs
CALL_FIELDS = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
CALL_TOKENS = ("DE", "QRZ", "CQ")
NCALL_TOKENS_PLUS_MAX22 = 2_063_592 + 4_194_304
GRID_RR73s = ('', '', 'RRR', 'RR73', '73')
FT8_MSG_FORMAT = (("i3", 3), ("grid", 16), ("callB",29), ("callA",29))

def get_fields(bits, fmt):
    out = {}
    for name, n in fmt:
        mask = (1 << n) - 1
        out[name] = bits & mask
        bits >>= n
    return out

def unpack(bits77):
    fields = get_fields(bits77, FT8_MSG_FORMAT)
    return (decode_call(fields["callA"]), decode_call(fields["callB"]), decode_grid(fields["grid"]))

def decode_call(call_int):
    portable = call_int & 1
    call_int >>= 1
    if call_int < 3:
        return CALL_TOKENS[call_int]
    call_int -= NCALL_TOKENS_PLUS_MAX22
    if call_int == 0:
        return '<...>'
    chars = []
    for alphabet, div in CALL_FIELDS:
        idx, call_int = divmod(call_int, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    return call + '/P' if portable else call

def decode_grid(grid_int):
    g15 = grid_int & 0x7FFF
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        return chr(65+a) + chr(65+b) + str(c) + str(d)
    r = g15 - 32400
    if r <= 4:
        return GRID_RR73s[r]
    snr = r - 35
    ir = grid_int >> 15
    prefix = 'R' if ir else ''
    return prefix + f"{snr:+03d}"
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

#============== LDPC ========================================================
class LdpcDecoder:
    def __init__(self):
        self.CV6idx = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
        self.CV7idx = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)
        self.mC2V_prev6 = None
        self.mC2V_prev7 = None
        
    def calc_ncheck(self, llr):
        bits6 = llr[self.CV6idx] > 0
        self.parity6 = np.sum(bits6, axis=1) & 1
        bits7 = llr[self.CV7idx] > 0
        self.parity7 = np.sum(bits7, axis=1) & 1
        return int(np.sum(self.parity7) + np.sum(self.parity6))

    def _pass_messages(self, llr, CVidx, mC2V_prev, update_collector):
        if mC2V_prev is None:
            mC2V_prev = np.zeros(CVidx.shape, dtype=np.float32)
        mV2C = llr[CVidx] - mC2V_prev
        tanh_mV2C = np.tanh(-mV2C)
        tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
        tanh_mC2V = tanh_mC2V / (tanh_mV2C + 0.001)
        alpha_atanh_approx = 1.18
        mC2V_curr  = tanh_mC2V / ((tanh_mC2V - alpha_atanh_approx) * (alpha_atanh_approx + tanh_mC2V))
        np.add.at(update_collector, CVidx, mC2V_curr - mC2V_prev)
        return mC2V_curr
    
    def do_ldpc_iteration(self, llr):
        update_collector = np.zeros_like(llr)
        self.mC2V_prev6 = self._pass_messages(llr, self.CV6idx, self.mC2V_prev6, update_collector)
        self.mC2V_prev7 = self._pass_messages(llr, self.CV7idx, self.mC2V_prev7, update_collector)
        llr += update_collector
        return llr, self.calc_ncheck(llr)

#============== AUDIO ========================================================
class AudioIn:
    def __init__(self, input_device_keywords, max_freq):
        self.fft_len = int(params['BPT'] * params['SAMP_RATE'] // params['SYM_RATE'])
        fft_out_len = self.fft_len // 2 + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / params['SAMP_RATE'])
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_in = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_window = fft_window=np.hanning(self.fft_len).astype(np.float32)
        self.hops_per_cycle = int(params['T_CYC'] * params['SYM_RATE'] * params['HPS'])
        self.hops_per_grid = 2 * self.hops_per_cycle
        self.dBgrid_main = np.ones((self.hops_per_grid, self.nFreqs), dtype = np.float32)
        indev = self.find_device(input_device_keywords)
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = params['SAMP_RATE'], input = True, input_device_index = indev,
            frames_per_buffer = int(params['SAMP_RATE'] / (params['SYM_RATE'] * params['HPS'])), stream_callback=self._callback,)
        self.dBgrid_main_ptr = int(cycle_time() * params['SYM_RATE']*params['HPS'])
        self.stream.start_stream()

    def find_device(self, device_str_contains):
        pya = pyaudio.PyAudio()
        for dev_idx in range(pya.get_device_count()):
            name = pya.get_device_info_by_index(dev_idx)['name']
            match = True
            for pattern in device_str_contains:
                if (not pattern in name): match = False
            if(match):
                return dev_idx
        print(f"[Audio] No audio device found matching {device_str_contains}")

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        np.multiply(self.audio_buffer, self.fft_window, out=self.fft_in)
        z = np.fft.rfft(self.fft_in)[:self.nFreqs]
        self.dBgrid_main[self.dBgrid_main_ptr, :] = 10*np.log10(z.real*z.real + z.imag*z.imag + 1e-12)
        self.dBgrid_main_ptr = (self.dBgrid_main_ptr + 1) % self.hops_per_grid
        return (None, pyaudio.paContinue)

# ================== WATERFALL ======================================================
class FT8Box:
    def __init__(self, ax, tbin, fbin, text):
        from matplotlib.patches import Rectangle
        self.ax = ax
        self.fbin = fbin
        self.patch = ax.add_patch(Rectangle((tbin, fbin), width=79*params['HPS'], height=8*params['BPT'],
                                            facecolor='blue',alpha=0.6, edgecolor='lime', lw=2))
        self.text = ax.text(tbin, fbin+2,text, color='white', fontsize='small', fontweight='bold' )
        self.modified = time.time()
    def update(self, tbin, text):
        self.patch.set_x(tbin)
        self.text.set_x(tbin)
        self.text.set_text(text)
        self.modified = time.time()

class Waterfall:
    def __init__(self, dBgrid, params):
        from matplotlib.animation import FuncAnimation
        self.dBgrid = dBgrid
        self.params = params
        self.boxes = []
        self.decode_queue = queue.Queue()
        self.fig, self.ax = plt.subplots(figsize=(10,10))
        self.fig.suptitle("G1OJS MiniPyFT8 with LDPC in ~ 300 lines")
        plt.tight_layout()
        self.ax.set_axis_off()
        self.image = self.ax.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        self.ani = FuncAnimation(self.fig,self._animate,interval=40,frames=(100000), blit=True)

    def tidy(self):
        for b in self.boxes:
            if (time.time() - b.modified) > params['WFBOX_LIFETIME']:
                b.patch.set_visible(False)
                b.text.set_visible(False)
        self.boxes = [b for b in self.boxes if b.patch.get_visible()]

    def post_decode(self, tbin, fbin, text):
        self.decode_queue.put((tbin, fbin, text))

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            tbin, fbin, text = self.decode_queue.get()
            self._add_or_update_box(tbin, fbin, text)
        if (frame % 10 == 0):
            self.tidy()
        return [self.image, *self.ax.patches, *self.ax.texts]

    def _add_or_update_box(self, tbin, fbin, text):
        for box in self.boxes:
            if box.fbin == fbin and abs(box.patch.get_x() - tbin) < 100:
                box.update(tbin, text)
                return
        self.boxes.append(FT8Box(self.ax, tbin, fbin, text))
                
# ================== CYCLE MANAGER ======================================================
def cycle_time():
    return time.time() % params['T_CYC']

def cyclestart_str(t):
    cyclestart_time = params['T_CYC'] * int( t / params['T_CYC'] )
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))
         
def cycle_manager(audio_in, freq_range, on_decode, silent, waterfall):
    ldpc = LdpcDecoder()
    nFreqs = audio_in.nFreqs
    dt = 1.0 / (params['SYM_RATE'] * params['HPS']) 
    df = freq_range[1] / (nFreqs -1)
    payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
    base_payload_hops = np.array([params['HPS'] * s for s in payload_symb_idxs])
    hop_idxs_Costas =  np.arange(7) * params['HPS']
    base_freq_idxs = np.array([params['BPT'] // 2 + params['BPT'] * t for t in range(8)])
    syncs = [{}] * nFreqs
    origins_for_decode = [(0, 0)] * nFreqs
    csync = np.full((7, 8*params['BPT']), -1/7, np.float32)
    for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
        fbins = range(tone* params['BPT'], (tone+1) * params['BPT'])
        csync[sym_idx, fbins] = 1.0
        csync[sym_idx, 7 * params['BPT']:] = 0.0
    csync_flat =  csync.ravel()
    duplicates_filter = []
    
    while True:
        # Search
        delay = params['T_SEARCH_1'] - cycle_time()
        if (delay > 0): time.sleep(delay)
        if (delay < 0): print(f"WARNING: decoding taking too long, delayed search by {-delay:5.1f} seconds")
        cycle = audio_in.dBgrid_main_ptr // audio_in.hops_per_cycle
        cycle_h0 = cycle * audio_in.hops_per_cycle
        if not silent:
            print("=================================================")
            print("Cycle         Time dt     sy nits Sigma Message")
        origins_for_decode = [(0, 0)] * nFreqs
        for fb in range(nFreqs - 8 * params['BPT']):
            freq_idxs = fb + base_freq_idxs
            p_dB = audio_in.dBgrid_main[:, fb:fb+8*params['BPT']]
            syncs[fb] = {'h0_idx':0, 'score':0, 'dt': 0}
            for h0_idx in range(cycle_h0 + params['H0_RANGE'][0], cycle_h0 + params['H0_RANGE'][1]):
                sync_score = float(np.dot(p_dB[h0_idx + hop_idxs_Costas + 36 * params['HPS'], :].ravel(), csync_flat))
                test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * dt - 0.7}
                if test_sync['score'] > syncs[fb]['score']:
                    syncs[fb] = test_sync
                    origins_for_decode[fb] = (syncs[fb]['h0_idx'], fb)
        # Decode
        duplicates_filter = []
        cs = cyclestart_str(time.time())
        origins_for_decode.sort(key = lambda o: o[0])
        while len(origins_for_decode):
            origins_for_decode = [o for o in origins_for_decode if o[0] is not None]
            for idx, origin in enumerate(origins_for_decode[:10]):
                time.sleep(0.005)
                ptr_rel_to_h0 = (audio_in.dBgrid_main_ptr - origin[0]) % audio_in.hops_per_grid
                if 0 <=  ptr_rel_to_h0 <= params['PAYLOAD_SYMBOLS'] * params['HPS']:
                    continue
                hops, freq_idxs = origin[0] + base_payload_hops, origin[1] + base_freq_idxs
                p_dB = audio_in.dBgrid_main[np.ix_(hops, freq_idxs)]
                p = np.clip(p_dB - np.max(p_dB), -80, 0)
                llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
                llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
                llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
                llr = np.column_stack((llra, llrb, llrc))
                llr = llr.ravel() / 10
                llr_sd = int(0.5+100*np.std(llr))/100.0
                llr = 3.5 * llr / (llr_sd + 0.01)
                llr = np.clip(llr, -3.7, 3.7)
                if llr_sd > params['MIN_LLR_SD']:
                    ldpc_it = 0
                    ncheck = ldpc.calc_ncheck(llr)
                    ncheck0 = ncheck
                    if ncheck > 0:
                        if ncheck <= params['LDPC_CONTROL'][0]:
                            for ldpc_it in range(params['LDPC_CONTROL'][1]):
                                llr, ncheck = ldpc.do_ldpc_iteration(llr)
                                if(ncheck == 0):
                                    break                    
                    if ncheck == 0:
                        bits91_int = 0
                        for bit in (llr[:91] > 0).astype(int).tolist():
                            bits91_int = (bits91_int << 1) | bit
                        bits77_int = check_crc(bits91_int)
                        if(bits77_int):
                            msg = unpack(bits77_int)
                            if(msg not in duplicates_filter):
                                fb = origin[1]
                                waterfall.post_decode(syncs[fb]['h0_idx'], fb, ' '.join(msg))
                                duplicates_filter.append(msg)
                                decode_dict = {'decoder': 'PyFT8', 'cs':cs, 'dt':syncs[fb]['dt'], 'f':0, 'sync_idx': 1, 'sync': syncs[fb],
                                               'msg_tuple':msg, 'msg':' '.join(msg), 'ncheck0': 99,'snr': -30,'llr_sd':0,'decode_path':'','td': cycle_time() }
                                if(on_decode):
                                    on_decode(decode_dict)
                                if(not silent):
                                    print(f"{decode_dict['cs']} {decode_dict['td']:4.2f} {decode_dict['sync']['dt']:+4.2f} {decode_dict['sync_idx']:3d} {ldpc_it:3d} {llr_sd:5.2f}  {' '.join(msg)}")
                origins_for_decode[idx] = (None, None)

if __name__ == "__main__":
    audio_in = AudioIn(['Mic', 'CODEC'], 3100)
    waterfall = Waterfall(audio_in.dBgrid_main, params)
    threading.Thread(target = cycle_manager, args =(audio_in, [200, 3100], None, False, waterfall,), daemon=True ).start()
    plt.show()  

