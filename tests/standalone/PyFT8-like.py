#!/usr/bin/env python3

import os, sys
import numpy as np
import wave

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
sys.path.insert(0, repo_root)

HPS=4
BPT=2
SYM_RATE =6.25
SAMP_RATE=12000
T_CYC=15
t2h = HPS/0.16
MIN_LLR_SD= 0.0
LDPC_CONTROL = (45, 12) 
H0_RANGE = [int(0 *t2h), int(5*t2h)]

BASE_FREQ_IDXS = np.array([BPT // 2 + BPT * t for t in range(8)])
symbol_idxs = list(range(7, 36)) + list(range(43, 72))
BASE_PAYLOAD_HOPS = np.array([HPS * s for s in symbol_idxs])
LAST_BASE_PAYLOAD_HOP = BASE_PAYLOAD_HOPS[-1]
COSTAS = [3,1,4,0,6,5,2]
BASE_COSTAS_HOPS =  np.arange(7) * HPS
HOPS_PER_CYCLE = int(T_CYC * SYM_RATE * HPS)

#=========== Unpacking functions ========================================
def get_bitfields(bits, lengths):
    fields = []
    for n in lengths:
        mask = (1 << n) - 1
        fields.append(bits & mask)
        bits >>= n
    return *fields, bits

def unpack(bits):
    i3, bits74 = get_bitfields(bits,[3])
    if i3 == 0:
        n3, bits71 = get_bitfields(bits74,[3])
        if n3 == 0:
            return ('Free text','not','implemented')
        else:
            return (['DXpedition','Field Day', 'Field Day', 'Telemetry'][n3-1],'not','implemented')
    elif i3 == 1 or i3 == 2: # 1 = Std Msg incl /R 2 = 'EU VHF' = Std Msg incl /P
        return unpack_std(bits74, i3)
    elif i3 == 3:
        return ('RTTY RU','not','implemented')
    elif i3 == 4:
        cq, rrr, swp, c58, hsh, _ = get_bitfields(bits74, [1,2,1,58,12]) 
        ca = "CQ" if cq else  '<....>'
        cb = ""
        for i in range(12):
            cb = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"[c58 % 38] + cb
            c58 = c58 // 38
        cb =  cb.strip()
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
    return (call_29(ca29, i3), call_29(cb29, i3), grid_rpt)

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
        return '<....>'
    else:
        call = standard_call28(call_int28, i3)
        if portable_rover:
            call = call + ('/P' if i3 == 2 else '/R')
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
    def __init__(self, wav_path, freq_range=[00, 3100]):
        self.fft_len = int( BPT * SAMP_RATE // SYM_RATE)
        fft_out_len = self.fft_len // 2 + 1
        max_freq = freq_range[1]
        self.nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_in = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_window = fft_window=np.hanning(self.fft_len).astype(np.float32)
        self.dBgrid_main = np.ones((HOPS_PER_CYCLE * 2, self.nFreqs), dtype = np.float32) 
        samples_perhop = int(SAMP_RATE / (SYM_RATE * HPS))
        self.dBgrid_main_ptr = 0

        wf = wave.open(wav_path, "rb")
        frames = wf.readframes(samples_perhop)
        while frames:
            self.process_hop(frames)
            frames = wf.readframes(samples_perhop)
        wf.close()    
                                   
    def process_hop(self, in_data):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        np.multiply(self.audio_buffer, self.fft_window, out=self.fft_in)
        z = np.fft.rfft(self.fft_in)[:self.nFreqs]
        self.dBgrid_main[self.dBgrid_main_ptr, :] = 10*np.log10(z.real*z.real + z.imag*z.imag + 1e-12)
        self.dBgrid_main_ptr +=1

def run():
    with open('test.txt','w') as f:
        f.write('')
    print("start")
    audio_in = AudioIn("test_01.wav")
    print("created instances")
    nFreqs = audio_in.nFreqs
    dt = 1.0 / (SYM_RATE * HPS)
    syncs = [{}] * nFreqs
    origins_for_decode = [(0, 0)] * nFreqs
    csync = np.full((7, 7 * BPT), -1/6, np.float32)
    for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
        fbins = range(tone * BPT, (tone+1) * BPT)
        csync[sym_idx, fbins] = 1.0
    csync_flat =  csync.ravel()
    
    # Search
    origins_for_decode = [(0, 0)] * nFreqs
    for fb in range(nFreqs - 8 * BPT):
        freq_idxs = fb + BASE_FREQ_IDXS
        p_dB = audio_in.dBgrid_main[:, fb:fb+7*BPT]
        syncs[fb] = {'h0_idx':0, 'score':0, 'dt': 0}
        for h0_idx in range(H0_RANGE[0], H0_RANGE[1]):
            sync_score = float(np.dot(p_dB[h0_idx + BASE_COSTAS_HOPS + 36 * HPS, :].ravel(), csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * dt - 0.7}
            if test_sync['score'] > syncs[fb]['score']:
                syncs[fb] = test_sync
                origins_for_decode[fb] = (syncs[fb]['h0_idx'], fb)
    print("finished search")
    
    # Decode
    messages = {}
    origins_for_decode = [o for o in origins_for_decode if o[0] is not None]
    target_params = [3.5, 3.7]
    for origin in origins_for_decode:    
        hops, freq_idxs = origin[0] + BASE_PAYLOAD_HOPS, origin[1] + BASE_FREQ_IDXS
        dBgrid = audio_in.dBgrid_main[np.ix_(hops, freq_idxs)]
        pmax = np.max(dBgrid)
        snr = np.clip(int(pmax - np.min(dBgrid) - 58), -24, 24)
        p = np.clip(dBgrid - pmax, -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc))
        llr = llr.ravel() / 10
        llr_sd = int(0.5+100*np.std(llr))/100.0
        llr = target_params[0] * llr / (1e-12 + llr_sd)
        llr = np.clip(llr, -target_params[1], target_params[1])
        if llr_sd > MIN_LLR_SD:
            ldpc = LdpcDecoder()
            ncheck = ldpc.calc_ncheck(llr)
            ncheck0 = ncheck
            if ncheck > 0:
                if ncheck <= LDPC_CONTROL[0]:
                    for ldpc_it in range(LDPC_CONTROL[1]):
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
                    h0_idx, fb = origin
                    if(msg not in messages):
                        messages[msg] = f"{1+len(messages):03d}:{msg}{(6.25*fb/BPT, 0.16*h0_idx/HPS)} {llr_sd}"

    with open('test.txt','a') as f:    
        for msg in messages:
            f.write(f"{messages[msg]}\n")
            print(messages[msg])

if __name__ == "__main__":
    run()
    
