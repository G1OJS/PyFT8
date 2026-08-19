import threading
import numpy as np
import pyaudio
from PyFT8.time_utils import time_utils
from PyFT8.decoders import ldpc_decode, osd_012, crc_unpack91

WATERFALL_DOWNSAMPLE = 2
DEBUG_PRINTS = True
T_CYC = 15
N_SYMS = 79
SYM_RATE = 6.25
SAMP_RATE = 12000
COSTAS = [3,1,4,0,6,5,2]
PAYLOAD_SYMB_IDXS = list(range(7, 36)) + list(range(43, 72))
COSTAS_SYMB_IDXS = list(range(7)) + list(range(36,43)) + list(range(72,79))



#============== CANDIDATE ===========================================================

ap_patterns = [
                ['NoAP',     0, []                                                               ], 
                ['CQ',       0, [0,0,0,0,0 ,0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0, 0,1,0,0] ],
                ['RR73',    58, [0,1, 1,1,1,1,1, 0,0,1,1,1, 0,1,0,1,0, 0,1]                      ],
                ['73',      58, [0,1, 1,1,1,1,1, 0,1,0,0,1, 0,1,0,0,0, 0,1]                      ],
                ['RRR',     58, [0,1, 1,1,1,1,1, 0,1,0,0,1, 0,0,1,0,0, 0,1]                      ],
              ]

class Candidate:
    def __init__(self, origin, search_grid_bounds, payload_on_search_grid, get_cycle_spectrum, on_message, llr_sd_min = 5):
        self.origin = origin
        self.search_grid_bounds = search_grid_bounds
        self.payload_on_search_grid = payload_on_search_grid
        self.get_cycle_spectrum = get_cycle_spectrum
        self.on_message = on_message
        self.llr_sd = 0
        self.llr_sd_min = llr_sd_min
        self.ipass = 0
        self.csync_7x7 = None
        self.signal_grid = None
        self.source = None
        self.tweaks = f"t:{0:+03d} f:{0:+03d}"
        self.saved_llrs = []
        self.decode_result = None
        self.n_sync_matches = 100
        self.fft2_len = 3200
        self.reused_spectrum_array = np.zeros(self.fft2_len, dtype = np.complex64)
        self.serial_id = None
        self.decode_notes = ''

    def check_and_package(self, duplicate_filter):
        self.msg_text = ' '.join(self.decode_result)
        key = self.origin['cyclestart_string'] + self.msg_text
        if (key not in duplicate_filter):
            duplicate_filter.add(key)
            o = self.origin
            decode_notes = self.decode_notes + self.tweaks
            tsec, fHz = o['tsec'], o['fHz']
            their_snr = f"{self.snr:+03d}"
            all_txt_format = f"{o['cyclestart_string']} {their_snr} {(tsec-0.6):4.1f} {fHz:4.0f} ~ {self.msg_text}"
            message = { "band":o['band'], "tsec":tsec, "fHz":fHz, "msg_tuple":self.decode_result,
                        "their_snr": their_snr, "their_tx_cycle":o['odd_even'],
                        "all_txt_format": all_txt_format, 'cyclestart_string':o['cyclestart_string'],
                        "decode_completed": time_utils.time(),  'tweaks':self.tweaks, 'decode_notes':decode_notes}
            self.on_message(message)
        self.decode_result = 'stop'

    def decode(self, current_max_ipass):
        time_utils.sleep(0)
        if (self.ipass <= current_max_ipass) and (self.decode_result != 'stop'):
            
            if self.ipass == 0:
                self._get_llr_grid()
                self.llr0 = self.llr.copy()
                for ap_pattern in ap_patterns:
                    self._set_AP(ap_pattern)
                    self._decode_good91()
                    self._decode_ldpc(35, 5, False)
            
            if self.ipass == 1:
                self._get_llr_fine()

            if self.ipass == 2:
                self.llr0 = self.llr.copy()
                for ap_pattern in ap_patterns[:2]:
                    self._set_AP(ap_pattern)
                    self._decode_good91()     
            if self.ipass == 3:
                for ap_pattern in ap_patterns[:2]:
                    self._set_AP(ap_pattern)
                    self._decode_ldpc(35, 5, False)
            if self.ipass == 4:
                for ap_pattern in ap_patterns:
                    self._set_AP(ap_pattern)
                    self._decode_ldpc(90, 20, True)
            if self.ipass == 5:
                for ap_pattern in ap_patterns:
                    self._set_AP(ap_pattern)
                    self._decode_osd()
            if self.ipass == 6:
                for pat_llr in self.saved_llrs:
                    self.pat_name, self.llr = pat_llr
                    self._decode_osd()
            if self.ipass == 7:
                self.decode_result = 'stop'

            self.ipass +=1

    def _set_AP(self, ap_pattern):
        self.pat_name, b0, bit_pattern = ap_pattern
        self.llr = self.llr0.copy()
        for b, bval in enumerate(bit_pattern):
            self.llr[b0 + b] = (bval*2-1) * 5
        if self.pat_name == 'CQ':
            self.llr[74:76] = -5
            self.llr[76] = 5
            self.llr[57:59] = -5
                
    def _decode_good91(self):
        if not self.decode_result:
            self.decode_notes = f'{self.source}_{self.pat_name}_GOOD91 '
            self.decode_result = crc_unpack91(self.llr[:91])
                
    def _decode_ldpc(self, max_nc0, max_its, save_llr):
        if not self.decode_result:
            self.decode_notes = f'{self.source}_{self.pat_name}_LDPC{max_its}'
            self.decode_result, self.n_its, output_llr = ldpc_decode(self.llr, max_nc0, max_its)
            if save_llr and not self.decode_result and len(output_llr) == 174:
                self.saved_llrs.append((f"{self.pat_name}_LDPC{max_its}", output_llr))

    def _decode_osd(self):
        if not self.decode_result:
            self.decode_notes = f'{self.source}_{self.pat_name}_OSD'
            self.decode_result = osd_012(self.llr)

    def _get_llr_grid(self):
        self._dB_to_llr(self.payload_on_search_grid)
        self.source = 'grid'

    def _get_llr_fine(self):
        cycle_spectrum = self.get_cycle_spectrum()
        fHz, tsec = self.origin['fHz'], self.origin['tsec']
        fb_0 = int(0.5 + fHz * 192000 / SAMP_RATE )
        tb_0 = int(0.5 + tsec/0.005)
        ftweak, ttweak = 0, 0

        ttweaks = range(-8, 8, 2) # 32 steps = 1 symbol
        scores = []
        for ttweak in ttweaks:
            self._get_signal_grid_fine(cycle_spectrum, fb_0+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ttweak = ttweaks[np.argmax(scores)]

        ftweaks = range(-32, 33, 8) # 16 steps = 1Hz, 6.25Hz = 100 steps
        scores = []
        for ftweak in ftweaks:
            self._get_signal_grid_fine(cycle_spectrum, fb_0+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ftweak = ftweaks[np.argmax(scores)]

        self._get_signal_grid_fine(cycle_spectrum, fb_0+ftweak, tb_0+ttweak)
        self.tweaks= f" t:{ttweak:+03d} f:{ftweak:+03d}"

        costas_abs_grid = self.signal_grid[COSTAS_SYMB_IDXS, :]
        ccheck = np.argmax(costas_abs_grid, axis = 1) - (COSTAS * 3)
        self.n_sync_matches = len([c for c in ccheck if c == 0])
        if self.n_sync_matches > 6:
            self.origin.update({'tsec': float(self.origin['tsec'] + ttweak / 200),
                                'fHz':float(self.origin['fHz'] + ftweak / 16) })
            payload_dB_grid = 20*np.log10(self.signal_grid[PAYLOAD_SYMB_IDXS, :])
            self._dB_to_llr(payload_dB_grid)
        else:
            self.decode_result = 'stop'

    def _get_signal_grid_fine(self, cycle_spectrum, fb_0, tb_0):
        self.source = 'fine'
        fft1_len = len(cycle_spectrum)
        
        # downsample to 32 samples per symbol / 200 samples per sec
        self.reused_spectrum_array[:850] = cycle_spectrum[fb_0:fb_0+850]
        self.reused_spectrum_array[-150:] = cycle_spectrum[fb_0-150:fb_0]
        candidate_zsig = np.fft.ifft(self.reused_spectrum_array)

        # get candidate symbol spectra x79 with df = 1 tone spacing
        symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
        idx = tb_0 + np.arange(N_SYMS)*32
        idx = np.clip(idx, 0, len(candidate_zsig)-32)
        symbols = np.empty((N_SYMS,32), dtype=np.complex64)
        for j, i0 in enumerate(idx):
            symbols[j,:] = candidate_zsig[i0:i0+32]
        self.signal_grid = np.abs(np.fft.fft(symbols, axis=1)[:, :8])

        if self.csync_7x7 is None:
            csync = np.full((7, 7), -1/6, np.float32)
            for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
                csync[sym_idx, tone] = 1.0
            self.csync_7x7 =  csync.ravel()
        #s0 = float(np.dot(self.signal_grid[:7, :7].ravel(), self.csync_7x7))
        s1 = float(np.dot(self.signal_grid[36:43, :7].ravel(), self.csync_7x7))
        #s2 = float(np.dot(self.signal_grid[72:, :7].ravel(), self.csync_7x7))
        #self.score = np.max([s0, s1, s2])
        self.score = s1

    def _dB_to_llr(self, payload_dB_grid):
        if payload_dB_grid is None:
            return
        p = payload_dB_grid 
        self.snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        mean = np.mean(llr)
        var = np.mean(llr*llr) - mean*mean
        self.llr_sd = np.sqrt(var)
        self.llr = 2.83 * llr / self.llr_sd
        if self.llr_sd <= self.llr_sd_min:
            self.decode_result = 'stop'

#============== AUDIO IN ===========================================================
class AudioIn:
    def __init__(self, search_freq_range, input_device_keywords):
        self.input_device_idx = None
        self.search_hps, self.search_bpt = 4, 2
        self.search_freq_range = search_freq_range
        self.search_fft_len = int(self.search_bpt * SAMP_RATE // SYM_RATE)
        self.search_fft_in = np.zeros(self.search_fft_len, dtype=np.float32)
        self.samples_perhop = int(SAMP_RATE / (SYM_RATE * self.search_hps))
        self.df = SYM_RATE / self.search_bpt
        self.search_f0_idx_range = [int(self.search_freq_range[0] / self.df),
                                    int((self.search_freq_range[1]) / self.df)]
        self.search_fft_window = np.hanning(self.search_fft_len).astype(np.float32)
        self.search_hops_per_cycle = int(T_CYC * SYM_RATE * self.search_hps)
        self.search_hops_per_grid = 2*self.search_hops_per_cycle
        self.dt = T_CYC / self.search_hops_per_cycle
        self.search_grid = np.ones((self.search_hops_per_grid, self.search_f0_idx_range[1]  + 8 * self.search_bpt ), dtype = np.float32)
        self.samples_per_cycle = int(SAMP_RATE * T_CYC)

        self.search_grid_ptr = int(time_utils.grid_time() * self.search_hops_per_grid / (2 * T_CYC))
        self.last_get_cycle_spectrum = 0
        self.last_get_hop_spectrum = 0
        self.waterfall_data = self._set_waterfall_data()
       
        self.audio_buffer = np.zeros(self.samples_per_cycle, dtype=np.float32)
        self.fft1_buffer  = np.zeros(192000, dtype=np.float32)
        self._find_input_device(input_device_keywords)

        threading.Thread(target = self._load_streamed_audio, daemon=True).start()

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
        self.stream.start_stream()
            
    def _set_waterfall_data(self):
        downsample = WATERFALL_DOWNSAMPLE
        data = self.search_grid[::downsample,::downsample].T
        df, dt = self.df * downsample, self.dt * downsample
        sig_w, sig_h = int(79*self.search_hps/downsample), int(8*self.search_bpt/downsample)
        pixels_per_cycle = int(self.search_hops_per_cycle / downsample)
        return {'data':data, 'df':df, 'dt':dt, 'sig_w':sig_w, 'sig_h':sig_h, 'pixels_per_cycle':pixels_per_cycle}

    def get_cycle_spectrum(self):
        if self.search_grid_ptr != self.last_get_cycle_spectrum:
            samps_offset = (T_CYC - time_utils.cycle_time()) * SAMP_RATE
            self.fft1_buffer[:self.samples_per_cycle] = np.roll(self.audio_buffer[-self.samples_per_cycle:], - samps_offset)
            self.cycle_spectrum = np.fft.rfft(self.fft1_buffer)
            self.last_get_cycle_spectrum = self.search_grid_ptr
        return self.cycle_spectrum
            
    def get_hop_spectrum(self, grid_ptr):
        if grid_ptr != self.last_get_hop_spectrum:
            np.multiply(self.audio_buffer[-self.search_fft_len:], self.search_fft_window, out = self.search_fft_in)
            z = np.fft.rfft(self.search_fft_in)[:self.search_grid.shape[1]]
            self.search_grid[grid_ptr, :] = 20*np.log10(np.abs(z)+1e-12)
            self.last_get_hop_spectrum = grid_ptr
        
    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16)#.astype(np.float32)
        n = len(samples)
        self.audio_buffer[:-n] = self.audio_buffer[n:]
        self.audio_buffer[-n:] = samples
        self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid
        if self.search_grid_ptr == 0:
            tg = time_utils.grid_time()
            print(tg)
            if tg > 0.1:
                self.search_grid_ptr = int(tg * self.search_hops_per_grid / (2 * T_CYC))
        self.get_hop_spectrum(self.search_grid_ptr)
        return (None, pyaudio.paContinue)

#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, input_device_keywords, on_message, sync_score_min = 85, max_cands = 200,
                 search_freq_range = [100, 3000], search_time_range = [-2.5+0.6, 2.5+0.6],
                 verbose = False):
        self.audio_in = AudioIn(search_freq_range, input_device_keywords)
        self.on_message = on_message
        self.sync_score_min, self.max_cands = sync_score_min, max_cands
        self.candidates = []
        self.verbose = verbose
        self.search_h0_range = [int((t+0.5)*self.audio_in.search_hps*SYM_RATE) for t in search_time_range]
        self.search_start_hop = self.search_h0_range[1] + 43 * self.audio_in.search_hps
        dt = 1.0 / (SYM_RATE * self.audio_in.search_hps)
        self.base_search_hops = 36 * self.audio_in.search_hps + np.arange(7) * self.audio_in.search_hps 
        csync = np.full((7, 7 * self.audio_in.search_bpt), -1/6, np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            fbins = range(tone * self.audio_in.search_bpt, (tone+1) * self.audio_in.search_bpt)
            csync[sym_idx, fbins] = 1.0
        self.csync_search = csync.ravel()
        self.band = None
        self.cand_serial = 0
        
        time_utils.set_cycle_length(T_CYC)
        time_utils.tlog(f"[Receiver] Search hops {self.search_h0_range[0]:3d} to {self.search_h0_range[1]:3d}", verbose = self.verbose)
        time_utils.tlog(f"[Receiver] Start search at hop {self.search_start_hop:3d}", verbose = self.verbose)
        
        time_utils.sleep(0.5)
        threading.Thread(target=self.manage_cycle, daemon=True).start()
        
    def search(self, cyclestart_string, odd_even, search_f_idxs):
        cands = []
        cycle_h0 = odd_even * self.audio_in.search_hops_per_cycle
        hops_per_sig = self.audio_in.search_hps * PAYLOAD_SYMB_IDXS[-1]
        for f0_idx in search_f_idxs:
            self.cand_serial = (self.cand_serial + 1) % 1000
            p = self.audio_in.search_grid[:, f0_idx: f0_idx + 7*self.audio_in.search_bpt]
            origin = {'score':0}
            for h0_idx in range(self.search_h0_range[0], self.search_h0_range[1]):
                score = float(np.dot(p[h0_idx + cycle_h0 + self.base_search_hops + self.audio_in.search_hps, :].ravel(), self.csync_search))

                test_sync = {'h0_idx': h0_idx,  'f0_idx':f0_idx,
                             'tsec':   h0_idx / (self.audio_in.search_hps * SYM_RATE),
                             'fHz':    SYM_RATE * f0_idx / self.audio_in.search_bpt,
                             'score':  score}
                if test_sync['score'] > origin['score']:
                    origin = test_sync
            if origin['score'] > self.sync_score_min:
                h0, tsec = origin['h0_idx'], origin['tsec']
                origin.update({'cyclestart_string':cyclestart_string, 'band':self.band, 'odd_even':odd_even})
                search_grid_h0 = cycle_h0 + h0 + self.audio_in.search_hps
                search_grid_hn = cycle_h0 + h0 + hops_per_sig
                hops = np.array([(search_grid_h0 + self.audio_in.search_hps * s) % self.audio_in.search_hops_per_grid for s in PAYLOAD_SYMB_IDXS])
                freqs = np.array([origin['f0_idx'] + self.audio_in.search_bpt//2 + t * self.audio_in.search_bpt for t in range(8)])
                payload_on_search_grid = self.audio_in.search_grid[hops,:][:, freqs]
                c = Candidate(origin, [search_grid_h0, search_grid_hn], payload_on_search_grid, self.audio_in.get_cycle_spectrum, self.on_message)
                c.serial_id = self.cand_serial
                cands.append(c)
   #     cands = [c for c in cands if not any(
  #                  [c2 for c2 in cands if c.serial_id != c2.serial_id
  #                     and np.abs(c2.origin['f0_idx'] - c.origin['f0_idx']) < 2
  #                       and np.abs(c2.origin['h0_idx'] - c.origin['h0_idx']) < 3])
  #              ]
        cands.sort(key = lambda c: c.origin['score'], reverse = True)
        return cands[:self.max_cands]

    def set_band(self, band):
        self.band = band

    def manage_cycle(self):
        dashes = "======================================================"
        duplicate_filter = set()
        time_utils.tlog(f"[Receiver] running", verbose = self.verbose)
        ptr_at_last_spectrum_calc = -1
        search_grid_ptr_prev = 0
        cycle_searched = False
        to_decode = []
        while True:
            time_utils.sleep(0.1)

            # reset cycle_searched at beginning of cycle
            if self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle < search_grid_ptr_prev:
                cycle_searched = False
            search_grid_ptr_prev = self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle

            # list candidates still to decode, and decode them
            to_decode = [c for c in self.candidates if (not c.decode_result) and (not (c.search_grid_bounds[0] <= self.audio_in.search_grid_ptr <= c.search_grid_bounds[1]))]
            if len(to_decode):
                ipasses = [c.ipass for c in to_decode]
                to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
                max_ipass = 10 +np.min(ipasses)
                for c in to_decode:
                    c.decode(max_ipass)
                    if c.decode_result is not None:
                        if c.decode_result != 'stop':
                            c.check_and_package(duplicate_filter)

            # if cycle not yet searched and search data available, search
            if not cycle_searched and self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle > self.search_start_hop:
                hstart = self.audio_in.search_grid_ptr
                tstart = time_utils.time()
                time_utils.tlog(f"[Cycle manager] start search at hop {hstart} ({time_utils.cycle_time():6.2f}s)", verbose = True)
                cyclestart_string = time_utils.cyclestart_string(time_utils.time())
                if len(to_decode):
                    time_utils.tlog(f"[Receiver] Warning - {len(to_decode)} candidates ran out of decoding time, ipass = {ipasses}", verbose = True)
                search_f_idxs = range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1])
                odd_even = time_utils.odd_even()
                self.candidates = self.search(cyclestart_string, odd_even, search_f_idxs)
                cycle_searched = True
                time_utils.tlog(f"[Cycle manager] New spectrum searched in {time_utils.time() - tstart:6.2f}s -> {len(self.candidates)} candidates", verbose = True) 

