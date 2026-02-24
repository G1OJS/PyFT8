import numpy as np
import time
import pyaudio
import threading

params = {'MIN_LLR_SD': 0.0,'HPS': 4, 'BPT':2,'SYM_RATE': 6.25,'SAMP_RATE': 12000, 'T_CYC':15, 
          'T_SEARCH_0': 4.6, 'T_SEARCH_1': 10.6,'T_DECODE': 14.8,'F_MAX': 3100}

params.update({'H0_RANGE': [-7 * params['HPS'], int(3.48 * params['SYM_RATE'] * params['HPS'])]})
print(params['H0_RANGE'])

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

#============== AUDIO ========================================================
class AudioIn:
    def __init__(self, input_device_keywords, max_freq):
        self.fft_len = int(params['BPT'] * params['SAMP_RATE'] // params['SYM_RATE'])
        fft_out_len = self.fft_len // 2 + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / params['SAMP_RATE'])
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_in = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_window = fft_window=np.hanning(self.fft_len).astype(np.float32)
        self.hops_percycle = int(params['T_CYC'] * params['SYM_RATE'] * params['HPS'])
        self.hop_dur = 1.0 / (params['SYM_RATE']*params['HPS'])
        self.dBgrid_main = np.ones((self.hops_percycle, self.nFreqs), dtype = np.float32)
        self.dBgrid_main_ptr = 0
        indev = self.find_device(input_device_keywords)
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = params['SAMP_RATE'], input = True, input_device_index = indev,
            frames_per_buffer = int(params['SAMP_RATE'] / (params['SYM_RATE'] * params['HPS'])), stream_callback=self._callback,)
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
        self.dBgrid_main_ptr = (self.dBgrid_main_ptr + 1) % self.hops_percycle
        return (None, pyaudio.paContinue)

audio_in = AudioIn(['Mic', 'CODEC'], params['F_MAX'])
nFreqs = audio_in.nFreqs
dt = 1.0 / (params['SYM_RATE'] * params['HPS']) 
df = params['F_MAX'] / (nFreqs -1)
csync = np.full((7, 8*params['BPT']), -1/7, np.float32)
for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
    fbins = range(tone* params['BPT'], (tone+1) * params['BPT'])
    csync[sym_idx, fbins] = 1.0
    csync[sym_idx, 7 * params['BPT']:] = 0.0
csync_flat =  csync.ravel()
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
data_symb_idxs = list(range(7, 36)) + list(range(43, 45))
base_payload_hops = np.array([params['HPS'] * s for s in payload_symb_idxs])
base_data_hops = np.array([params['HPS'] * s for s in data_symb_idxs])
hop_idxs_Costas =  np.arange(7) * params['HPS']
bpt = params['BPT']
base_freq_idxs = np.array([bpt // 2 + bpt * t for t in range(8)])
syncs = [{}] * nFreqs
duplicates_filter = []

import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(15,5))
wf_plot = ax.imshow(audio_in.dBgrid_main, vmax = 90, vmin = 60, origin = 'lower', interpolation = 'none')

def wait_for_time(s):
    while (time.time() %params['T_CYC'] < s):
        wf_plot.set_data(audio_in.dBgrid_main)
        plt.pause(0.05)

print("=================================================")
print("Time  Freq dt    sy Offs Sigma Message")

while True:

    wait_for_time(params['T_SEARCH_1'])
    dBgrid_main = audio_in.dBgrid_main
    for fb in range(nFreqs - 8 * params['BPT']):
        freq_idxs = fb + base_freq_idxs
        p_dB = dBgrid_main[:, fb:fb+8*params['BPT']]
        syncs[fb] = {'h0_idx':0, 'score':0, 'dt': 0}
        for h0_idx in range(params['H0_RANGE'][0], params['H0_RANGE'][1]):
            sync_score = float(np.dot(p_dB[h0_idx + hop_idxs_Costas + 36 * params['HPS'], :].ravel(), csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * dt - 0.7}
            if test_sync['score'] > syncs[fb]['score']:
                syncs[fb] = test_sync
                
    wait_for_time(params['T_DECODE'])
    duplicates_filter = []
    audio_in.dBgrid_main_ptr = 0
    dBgrid_main = audio_in.dBgrid_main
    for fb in range(nFreqs - 8 * params['BPT']):
        hops = syncs[fb]['h0_idx'] + base_data_hops
        freq_idxs = fb + base_freq_idxs
        p_dB = dBgrid_main[np.ix_(hops, freq_idxs)]
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
            llr = llr[:91]
            bits91_int = 0
            for bit in (llr > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            if(bits77_int):
                msg = unpack(bits77_int)
                if(msg not in duplicates_filter):
                    duplicates_filter.append(msg)
                    decode_dict = {'decoder': 'PyFT8', 'cs':f"{time.time() % params['T_CYC']:05.2f}", 'dt':syncs[fb]['dt'], 'f':0,
                             'sync_idx': 1, 'sync': syncs[fb], 'msg_tuple':msg, 'msg':' '.join(msg),
                             'ncheck0': 99,'snr': -30,'llr_sd':0,'decode_path':'','td': 0}
                    print(f"{decode_dict['cs']} {0:4d} {decode_dict['sync']['dt']:+4.2f} {decode_dict['sync_idx']} {0} {0} {' '.join(msg)}")

if __name__ == "__main__":
    mini_cycle_manager(silent = False)

