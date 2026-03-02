import threading
import numpy as np
import wave
import time
from PyFT8.time_utils import global_time_utils
import os
import pyaudio
from PyFT8.sigspecs import FT8
from PyFT8.utilities import tprint

LLR_SD_MIN = 0.5
HPS = 4
BPT =2
SYM_RATE = 6.25
SAMP_RATE = 12000
T_CYC = 15
LDPC_CONTROL = (45, 12) 

t2h = HPS/0.16
H0_RANGE = [int(-1 *t2h), int(3.4 *t2h)]
H_SEARCH_0 = H0_RANGE[1] + 7 * HPS
H_SEARCH_1 = H0_RANGE[1] + 43 * HPS 

BASE_FREQ_IDXS = np.array([BPT // 2 + BPT * t for t in range(8)])
symbol_idxs = list(range(7, 36)) + list(range(43, 72))
BASE_PAYLOAD_HOPS = np.array([HPS * s for s in symbol_idxs])
LAST_BASE_PAYLOAD_HOP = BASE_PAYLOAD_HOPS[-1]
BASE_COSTAS_HOPS =  np.arange(7) * HPS
HOPS_PER_CYCLE = int(T_CYC * SYM_RATE * HPS)

def cycle_time():
    return time.time() % T_CYC

def cyclestart_str(t):
    cyclestart_time = T_CYC * int( t / T_CYC )
    return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))


import numpy as np
import time
from PyFT8.FT8_unpack import unpack
from PyFT8.FT8_crc import check_crc
from PyFT8.ldpc import LdpcDecoder

params = {
'MIN_LLR_SD': 0.5,           # global minimum llr_sd
'LDPC_CONTROL': (45, 12),         # max ncheck0, max iterations         
}

class Candidate:
    def __init__(self):

        self.demap_started, self.decode_completed = False, False
        self.ncheck0, self.ncheck = 99, 99
        self.llr_sd = 0
        self.decode_path = ''
        self.decode_dict = False
        self.processing_time = 0
        self.cyclestart_str = ''
        self.msg = ''
        # decode_dict is set in spectrum search
        self.ldpc = LdpcDecoder()

    def _record_state(self, actor_code, final = False):
        finalcode = "#" if final else ""
        self.decode_path = self.decode_path + f"{actor_code}{self.ncheck:02d}{finalcode}"
        if(final):
            self.decode_completed = time.time()

    def demap(self, dBgrid_main, target_params = (3.3, 3.7)):
        self.demap_started = time.time()
        hops = np.clip(self.sync['h0_idx'] + BASE_PAYLOAD_HOPS, 0, HOPS_PER_CYCLE - 1)
        self.dB = dBgrid_main[np.ix_(hops, self.freq_idxs)]
        p = np.clip(self.dB - np.max(self.dB), -80, 0)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc))
        llr = llr.ravel() / 10
        self.llr_sd = int(0.5+100*np.std(llr))/100.0
        llr = target_params[0] * llr / (1e-12 + self.llr_sd)
        self.llr = np.clip(llr, -target_params[1], target_params[1])
        self.decode_dict.update({'llr_sd':self.llr_sd})
          
    def decode(self):
        decode_started = time.time()
        if(self.llr_sd < params['MIN_LLR_SD']):
            self._record_state("I", final = True)
            return
        self.ncheck = self.ldpc.calc_ncheck(self.llr)
        self.ncheck0 = self.ncheck
        self._record_state("I")

        if self.ncheck > 0:
            if self.ncheck <= params['LDPC_CONTROL'][0]:
                for it in range(params['LDPC_CONTROL'][1]):
                    self.llr, self.ncheck = self.ldpc.do_ldpc_iteration(self.llr)
                    self._record_state("L")
                    if(self.ncheck == 0):
                        break                    
        if(self.ncheck == 0):
            bits91_int = 0
            for bit in (self.llr[:91] > 0).astype(int).tolist():
                bits91_int = (bits91_int << 1) | bit
            bits77_int = check_crc(bits91_int)
            if(bits77_int):
                self.msg = unpack(bits77_int)

        self._record_state("M" if self.msg else "_", final = True)

        self.decode_dict.update( {
                            'msg_tuple':self.msg,
                            'msg':' '.join(self.msg),
                            'llr_sd':self.llr_sd,
                            'decode_path':self.decode_path,
                            'ncheck0': self.ncheck0,
                            'snr': np.clip(int(np.max(self.dB) - np.min(self.dB) - 58), -24, 24),
                            'td': f"{time.time() %60:4.1f}"
                           })
        

class AudioIn:
    def __init__(self, input_device_keywords, max_freq, wav_files = None):
        self.fft_len = int(BPT * SAMP_RATE // SYM_RATE)
        fft_out_len = self.fft_len // 2 + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
        self.audio_buffer = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_in = np.zeros(self.fft_len, dtype=np.float32)
        self.fft_window = fft_window=np.hanning(self.fft_len).astype(np.float32)
        self.hops_per_grid = 2 * HOPS_PER_CYCLE
        self.dBgrid_main = np.ones((self.hops_per_grid, self.nFreqs), dtype = np.float32)
        self.dBgrid_main_ptr = 0
        if input_device_keywords is not None:
            self.start_streamed_audio(input_device_keywords)
        elif wav_files is not None:
            threading.Thread(target = self.load_wavs, args =(wav_files,)).start()

    def load_wavs(self, wav_paths, hop_dt = 1 / (SYM_RATE * HPS) - 0.001):
        samples_perhop = int(SAMP_RATE / (SYM_RATE * HPS))
        for wav_path in wav_paths:
            wf = wave.open(wav_path, "rb")
            hoptimes = []
            th = time.time()
            frames = wf.readframes(samples_perhop)
            while frames:
                delay = hop_dt - (time.time()-th)
                if(delay>0): time.sleep(delay)
                th = time.time()
                hoptimes.append(th)
                self._callback(frames, None, None, None)
                frames = wf.readframes(samples_perhop)
            wf.close()
            deltas = np.diff(hoptimes)
            tprint(f"[Receiver] read wav file with hop mean = {1000*np.mean(deltas):6.2f}ms, sd =  {1000*np.std(deltas):6.2f}ms")
            
    def start_streamed_audio(self, input_device_keywords):
        indev = self.find_device(input_device_keywords)
        self.stream = pyaudio.PyAudio().open(
            format = pyaudio.paInt16, channels=1, rate = SAMP_RATE, input = True, input_device_index = indev,
            frames_per_buffer = int(SAMP_RATE / (SYM_RATE * HPS)), stream_callback=self._callback,)
        self.dBgrid_main_ptr = int(cycle_time() * SYM_RATE * HPS)
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
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        self.dBgrid_main[self.dBgrid_main_ptr, :] = 10*np.log10(p)
        self.dBgrid_main_ptr = (self.dBgrid_main_ptr + 1) % self.hops_per_grid
        return (None, pyaudio.paContinue)


class Receiver():
    def __init__(self, audio_in, freq_range, on_decode, waterfall):
        self.verbose = True
        self.sample_rate = 12000
        self.audio_in = audio_in
        self.sigspec = FT8
        self.fbins_pertone = 2
        self.hops_persymb = 4
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * self.hops_persymb)
        self.nFreqs = self.audio_in.nFreqs
        self.fbins_per_signal = self.sigspec.tones_persymb * self.fbins_pertone
        self.df = freq_range[1]/(self.audio_in.nFreqs - 1)
        self.dt = 1 / (HPS * SYM_RATE)
        self.f0_idxs = range(int(freq_range[0]/self.df),
                        min(self.audio_in.nFreqs - self.fbins_per_signal, int(freq_range[1]/self.df)))
        self.on_decode = on_decode
        self.csync_flat = self.make_csync(FT8)
        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def make_csync(self, sigspec):
        csync = np.full((sigspec.costas_len, self.fbins_per_signal), -self.fbins_pertone / (self.fbins_per_signal - self.fbins_pertone), np.float32)
        for sym_idx, tone in enumerate(sigspec.costas):
            fbins = range(tone * self.fbins_pertone, (tone+1) * self.fbins_pertone)
            csync[sym_idx, fbins] = 1.0
            csync[sym_idx, sigspec.costas_len*self.fbins_pertone:] = 0
        return csync.ravel()

    def get_sync(self, f0_idx, dB, sync_idx):
        best_sync = {'h0_idx':0, 'score':0, 'dt': 0}
        for h0_idx in range(H0_RANGE[0], H0_RANGE[1]):
            sync_score = float(np.dot(dB[h0_idx + BASE_COSTAS_HOPS + sync_idx * 36 * self.hops_persymb ,  :].ravel(), self.csync_flat))
            test_sync = {'h0_idx':h0_idx, 'score':sync_score, 'dt': h0_idx * self.dt - 0.7}
            if test_sync['score'] > best_sync['score']:
                best_sync = test_sync
        return best_sync

    def search(self, f0_idxs, cyclestart_str):
        cands = []
        dBgrid_main = self.audio_in.dBgrid_main
        hps, bpt = self.hops_persymb, self.fbins_pertone
        for f0_idx in f0_idxs:
            dB = dBgrid_main[:, f0_idx:f0_idx + self.fbins_per_signal]
            dB = dB - np.max(dB)
            c = Candidate()
            c.f0_idx = f0_idx
            sync_idx = 1
            c.sync = self.get_sync(f0_idx, dB, sync_idx)
            c.freq_idxs = [c.f0_idx + bpt // 2 + bpt * t for t in range(self.sigspec.tones_persymb)]
            c.last_payload_hop = c.sync['h0_idx'] + hps * 72
            c.cyclestart_str = cyclestart_str
            c.decode_dict = {'decoder': 'PyFT8',
                             'cs':c.cyclestart_str,
                             'f':int((c.f0_idx + bpt // 2) * self.df),
                             'f0_idx': c.f0_idx,
                             'sync_idx': sync_idx, 
                             'sync': c.sync,
                             'dt': int(0.5+100*c.sync['dt'])/100.0, 
                             'ncheck0': 99,
                             'snr': -30,
                             'llr_sd':0,
                             'decode_path':'',
                             'msg_tuple':(''), 'msg':'',
                             'td': 0}
            cands.append(c)
        return cands
        
    def manage_cycle(self):
        dashes = "======================================================"
        candidates = []
        duplicate_filter = set()
        rollover = global_time_utils.new_ticker(0)
        search = global_time_utils.new_ticker(11)
     
        def summarise_cycle():
            unfinished = [c for c in candidates if not c.decode_completed]
            nu = len(unfinished)
            if(self.verbose):
                with_message = [c for c in candidates if c.msg]
                failed = [c for c in candidates if c.decode_completed and not c.msg]
                ns, nf = len(with_message), len(failed)
                global_time_utils.tlog(f"[Cycle manager] Last cycle had {ns} decodes, {nf} failures and {nu} unfinished (total = {ns+nf+nu})")   

        self.audio_in.dBgrid_main_ptr = 0
        dBgrid_main_ptr_prev = 0
        base_pyld_hops = BASE_PAYLOAD_HOPS
        while True:
            time.sleep(0.001)
            ptr = self.audio_in.dBgrid_main_ptr
            if(ptr != dBgrid_main_ptr_prev):
                dBgrid_main_ptr_prev = ptr

                new_to_decode = []
                for c in candidates:
                    ptr_rel_to_h0 = (ptr - c.sync['h0_idx']) % self.hops_percycle
                    if not (base_pyld_hops[0] <= ptr_rel_to_h0 <= base_pyld_hops[-1]) and not c.demap_started:
                        c.demap(self.audio_in.dBgrid_main)
                    if c.llr_sd > 0 and not c.decode_completed:
                        new_to_decode.append(c)
                    if c.msg:
                        key = c.cyclestart_str + " " + " ".join(c.msg)
                        if key not in duplicate_filter:
                            duplicate_filter.add(key)
                            self.on_decode(c.decode_dict)
                new_to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
                for c in new_to_decode[:35]:
                    c.decode()

                if(global_time_utils.check_ticker(rollover)):
                    global_time_utils.tlog(f"{dashes}\n[Cycle manager] rollover detected at {global_time_utils.cycle_time():.2f}", verbose = self.verbose)
                    self.audio_in.dBgrid_main_ptr = 0
                if (global_time_utils.check_ticker(search)):
                    summarise_cycle()
                    global_time_utils.tlog(f"[Cycle manager] start search at hop { self.audio_in.dBgrid_main_ptr}", verbose = self.verbose)
                    candidates = self.search(self.f0_idxs, global_time_utils.cyclestart_str(time.time()))
                    global_time_utils.tlog(f"[Cycle manager] New spectrum searched -> {len(candidates)} candidates", verbose = self.verbose) 

        summarise_cycle() # for wav files that have just finished

                         
