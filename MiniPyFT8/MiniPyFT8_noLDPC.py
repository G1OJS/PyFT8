import numpy as np
import time
import pyaudio

params = {
'MIN_LLR_SD': 0.5,
'HPS': 4, 'BPT':2,
'SYM_RATE': 6.25,
'SAMP_RATE': 12000
}

offsets = np.geomspace(0.1,2,10)
offsets = [0] + list(-offsets[::-1]) +  list(offsets)

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

def unpack_ft8_c29(c29):
    c28 = c29 >> 1
    p1 = c29 & 1
    from string import ascii_uppercase as ltrs, digits as digs
    if c28<3:
        return ["DE", 'QRZ','CQ'][c28]
    n = c28 - 2_063_592 - 4_194_304 # NTOKENS, MAX22
    if n == 0:
        return '<...>'
    charmap = [' ' + digs + ltrs, digs + ltrs, digs + ' ' * 17] + [' ' + ltrs] * 3
    divisors = [36*10*27**3, 10*27**3, 27**3, 27**2, 27, 1]
    indices = []
    for d in divisors:
        i, n = divmod(n, d)
        indices.append(i)
    callsign = ''.join(t[i] for t, i in zip(charmap, indices)).strip()
    if(p1):
        callsign = callsign + "/P"
    return callsign

def unpack_ft8_g16(g16):
    ir = g16 >> 15
    g15 = g16 & 0b111111111111111
    if g15 < 32400:
        a, nn = divmod(g15,1800)
        b, nn = divmod(nn,100)
        c, d = divmod(nn,10)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}"
    r = g15 - 32400
    txt = ['','','RRR','RR73','73']
    if 0 <= r <= 4: return txt[r]
    snr = r-35
    R = '' if (ir == 0) else 'R'
    return f"{R}{snr:+03d}"

def unpack(bits77_int):
    i3 = bits77_int & 0b111
    grid_rpt = unpack_ft8_g16(bits77_int >> 3 & 0b1111111111111111)
    call_b   = unpack_ft8_c29(bits77_int >> 19 & 0b11111111111111111111111111111)
    call_a   = unpack_ft8_c29(bits77_int >> 48 & 0b11111111111111111111111111111)
    return (call_a, call_b, grid_rpt)

def find_device(device_str_contains):
    pya = pyaudio.PyAudio()
    for dev_idx in range(pya.get_device_count()):
        name = pya.get_device_info_by_index(dev_idx)['name']
        match = True
        for pattern in device_str_contains:
            if (not pattern in name): match = False
        if(match):
            return dev_idx
    print(f"[Audio] No audio device found matching {device_str_contains}")

class AudioIn:
    def __init__(self, input_device_keywords, max_freq):
        fft_len = int(params['BPT'] * params['SAMP_RATE'] // params['SYM_RATE'])
        fft_out_len = int(fft_len/2) + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / params['SAMP_RATE'])
        self.fft_window = fft_window=np.hanning(fft_len)
        self.audio_buffer = np.zeros(fft_len, dtype=np.float32)
        self.hops_percycle = int(15 * params['SYM_RATE'] * params['HPS'])
        self.dBgrid_main = np.zeros((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.grid_main_ptr = 0
        indev = find_device(input_device_keywords)
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = params['SAMP_RATE'],
            input = True, input_device_index = indev,
            frames_per_buffer = int(params['SAMP_RATE'] / (params['SYM_RATE'] * params['HPS'])), stream_callback=self._callback,)
        self.stream.start_stream()

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        z = np.fft.rfft(self.audio_buffer * self.fft_window)
        p = z.real*z.real + z.imag*z.imag
        self.dBgrid_main[self.grid_main_ptr] = 10*np.log10(p[:self.nFreqs]+1e-12)
        self.grid_main_ptr = (self.grid_main_ptr + 1) % self.hops_percycle
        return (None, pyaudio.paContinue)

class Spectrum:
    def __init__(self, input_device_keywords, freq_range):
        self.audio_in = AudioIn(input_device_keywords, freq_range[1])
        nFreqs = self.audio_in.nFreqs
        self.dt = 1.0 / (params['SYM_RATE'] * params['HPS']) 
        self.df = freq_range[1] / (nFreqs -1)
        self.h_search_0 = int(4.6/self.dt)
        self.h_search_1 = int(10.6/self.dt)
        self.hop_start_lattitude = int(3.48/self.dt)
        csync = np.full((7, 8*params['BPT']), -1/7, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            fbins = range(tone* params['BPT'], (tone+1) * params['BPT'])
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, 7 * params['BPT']:] = 0
        self.csync_flat =  csync.ravel()
        self.f0_idxs = range(int(freq_range[0]/self.df),
                    min(nFreqs - 8 * params['BPT'], int(freq_range[1]/self.df)))
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
        data_symb_idxs = list(range(7, 36)) + list(range(43, 45))
        self.base_payload_hops = np.array([params['HPS'] * s for s in payload_symb_idxs])
        self.base_data_hops = np.array([params['HPS'] * s for s in data_symb_idxs])
        
    def get_sync(self, f0_idx, dB, sync_idx):
        best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
        h0_min = 0 if sync_idx == 0 else -7*params['HPS']
        hop_idxs_Costas =  np.arange(7) * params['HPS']
        for h0_idx in range(h0_min, self.hop_start_lattitude):
            sync_score = float(np.dot(dB[h0_idx + hop_idxs_Costas + sync_idx * 36 * params['HPS'] ,  :].ravel(), self.csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * self.dt - 0.7}
            if test_sync['score'] > best_sync['score']:
                best_sync = test_sync
        return best_sync
    
    def search(self, cyclestart_str, sync_idx):
        cands = []
        hps, bpt = params['HPS'], params['BPT']
        for f0_idx in self.f0_idxs:
            c = Candidate(self.audio_in.dBgrid_main, f0_idx, self.df)
            c.sync = self.get_sync(f0_idx, c.dB, sync_idx)
            c.last_payload_hop = c.sync['h0_idx'] + hps * 72
            c.last_data_hop = c.sync['h0_idx'] + hps * 45
            c.cyclestart_str = cyclestart_str
            c.sync_idx = sync_idx
            cands.append(c)
        return cands

class Candidate:
    def __init__(self, dBgrid_main, f0_idx, df):
        self.decode_started, self.decode_completed = False, False
        self.msg, self.dt, self.td, self.fHz, self.snr, self.llr_sd, self.lev = '', 0, 0, 0, -30, 0, 0
        bpt = params['BPT']
        self.freq_idxs = [f0_idx + bpt // 2 + bpt * t for t in range(8)]
        self.fHz = int((f0_idx + bpt // 2) * df)
        self.dB = dBgrid_main[:, f0_idx:f0_idx + 8 * bpt]

    def demap(self, spectrum, target_params = (3.3, 3.7)):
        hops = self.sync['h0_idx'] + spectrum.base_data_hops
        p_dB = spectrum.audio_in.dBgrid_main[np.ix_(hops, self.freq_idxs)]
        p = np.clip(p_dB - np.max(p_dB), -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc))
        llr = llr.ravel() / 10
        self.llr_sd = int(0.5+100*np.std(llr))/100.0
        llr = target_params[0] * llr / self.llr_sd
        self.llr = np.clip(llr, -target_params[1], target_params[1])

    def decode(self, spectrum):
        if self.llr_sd > params['MIN_LLR_SD']:
            llr = self.llr[:91]
            for lev in offsets:
                bits91_int = 0
                for bit in (llr > lev).astype(int).tolist():
                    bits91_int = (bits91_int << 1) | bit
                bits77_int = check_crc(bits91_int)
                if(bits77_int):
                    self.msg = unpack(bits77_int)
                    self.lev = lev
                    break
        self.decode_completed = True

def cycle_manager(input_device_keywords = ['Mic', 'CODEC'], freq_range = [200, 3100], on_decode = None, silent = True):
    from PyFT8.time_utils import global_time_utils
    import time
    cands_list = []
    cands_list_1 = []
    duplicate_filter = set()
    time.sleep((14.5 - time.time()) %15)
    spectrum = Spectrum(input_device_keywords, freq_range)
    cycle_searched_1, cycle_searched_0  = False, False
    cycle_time_prev = 0
    while True:
        time.sleep(0.001)
        if(time.time()%15 < cycle_time_prev):
            if(not silent):
                print("=================================================")
                print("Time  Freq dt    sy Offs Sigma Message")
            cycle_searched_1, cycle_searched_0  = False, False
            spectrum.audio_in.grid_main_ptr = 0
            duplicate_filter = set()
        cycle_time_prev = time.time()%15

        ptr = spectrum.audio_in.grid_main_ptr

        if (ptr > spectrum.h_search_0 and not cycle_searched_0):
            cycle_searched_0 = True
            cands_list = spectrum.search("000000_000000", 0)

        if (ptr > spectrum.h_search_1 and not cycle_searched_1):
            cycle_searched_1 = True
            cands_list_1 = spectrum.search("000000_000000", 1)

        if(cycle_searched_1):
            for i, c_1 in enumerate(cands_list_1):
                c = cands_list[i]
                if(c.decode_completed and not c.msg and c.sync_idx == 0):
                    if (ptr > c_1.last_data_hop and not c_1.decode_started):
                        c_1.demap(spectrum)
                        cands_list.append(c_1)
                        cands_list.remove(c)
                        c = None

        for c in cands_list:
            if (ptr > c.last_data_hop and not c.decode_started):
                c.decode_started = True
                c.demap(spectrum)
                c.decode(spectrum)
                if(c.msg):
                    c.dedupe_key = ' '.join(c.msg)
                    if(not c.dedupe_key in duplicate_filter):
                        duplicate_filter.add(c.dedupe_key)
                        c.decode_dict = {'decoder': 'PyFT8',
                             'cs':global_time_utils.cyclestart_str(time.time()), 'dt':c.sync['dt'], 'f':c.fHz,
                             'sync_idx': c.sync_idx, 'sync': c.sync,
                             'msg_tuple':c.msg, 'msg':' '.join(c.msg),
                             'ncheck0': 99,'snr': -30,'llr_sd':0,'decode_path':'','td': 0}
                        if(on_decode):
                            on_decode(c.decode_dict)
                        if(not silent):
                            print(f"{time.time() %15:05.2f} {c.fHz:4d} {c.sync['dt']:+4.2f} {c.sync_idx} {c.lev:5.2f} {c.llr_sd:5.2f} {' '.join(c.msg)}")

def mini_cycle_manager(input_device_keywords = ['Mic', 'CODEC'], freq_range = [200, 3100], on_decode = None, silent = True):                            
    import threading
    threading.Thread(target = cycle_manager, args =(input_device_keywords, freq_range, on_decode, silent) ).start()


if __name__ == "__main__":
    mini_cycle_manager(silent = False)

