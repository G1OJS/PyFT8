import threading
import numpy as np
import pyaudio
from PyFT8.time_utils import time_utils
from PyFT8.decoders import ldpc_decode, osd_012, crc_unpack91
from PyFT8.transmitter import symbols_to_complex_audio, encode_bits77
import pickle

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
    def __init__(self, origin, signal_hop_bounds, payload_hop_bounds, payload_on_search_grid, get_cycle_spectrum, on_message, llr_sd_min = 5):
        self.origin = origin
        self.signal_hop_bounds = signal_hop_bounds
        self.payload_hop_bounds = payload_hop_bounds
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
        self.n_sync_matches_min = 6
        self.fft2_len = 3200
        self.reused_spectrum_array = np.zeros(self.fft2_len, dtype = np.complex64)
        self.serial_id = None
        self.decode_notes = ''
        self.subtracted = False
        self.new_after_subtraction = False
        self.post_subtraction_success = False
        self.snr = -30
        self.msg_text = ''
        self.msg_tuple = None
        self.has_neighbours = False

    def dump(self, file):
        with open(file, 'wb') as f:
            pickle.dump((self.origin, self.signal_grid), f)
  
    def refine_time_origin(self):
        fb_0 = int(0.5 + self.origin['fHz'] * 192000/SAMP_RATE )
        tb_0 = int(0.5 + self.origin['tsec'] * 200)
        tb_range = range(tb_0 - 6, tb_0 + 6) # 16 per 1/2 symbol
        score = -1e40
        origin_orig = self.origin_string()
        cycle_spectrum = self.get_cycle_spectrum()
        for fb in range(fb_0 -2, fb_0 +2):
            for tb in tb_range:
                self._get_signal_grid_fine(cycle_spectrum, fb_0, tb)
                if self.score > score:
                    score = self.score
                    self.origin['tsec'] = tb  / 200
                    self.origin['fHz'] =  fb  / 16

    def origin_string(self):
        return f"{self.origin['fHz']:6.2f}Hz {self.origin['tsec'] - 0.5:6.2f}s" 

    def check_and_package(self, duplicate_filter):
        self.msg_text = ' '.join(self.decode_result)
        self.msg_tuple = self.decode_result
        key = self.origin['cyclestart_string'] + self.msg_text
        if (key not in duplicate_filter):
            if self.new_after_subtraction:
                self.decode_notes += "_SUB"
            duplicate_filter.add(key)
            o = self.origin
            decode_notes = self.decode_notes
            tsec, fHz = o['tsec'], o['fHz']
            their_snr = f"{self.snr:+03d}"
            all_txt_format = f"{o['cyclestart_string']} {their_snr} {(tsec-0.5):7.3f} {fHz:7.3f} ~ {self.msg_text}"
            message = { "band":o['band'], "tsec":tsec, "fHz":fHz, "msg_tuple":self.decode_result,
                        "their_snr": their_snr, "their_tx_cycle":o['odd_even'],
                        "all_txt_format": all_txt_format, 'cyclestart_string':o['cyclestart_string'],
                        "decode_completed": time_utils.time(),  'tweaks':self.tweaks, 'decode_notes':decode_notes}
            self.on_message(message)
            self.post_subtraction_success = self.new_after_subtraction
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
            self.decode_result, self.bits77_int = crc_unpack91(self.llr[:91])
                
    def _decode_ldpc(self, max_nc0, max_its, save_llr):
        if not self.decode_result:
            self.decode_notes = f'{self.source}_{self.pat_name}_LDPC{max_its}'
            self.decode_result, self.n_its, output = ldpc_decode(self.llr, max_nc0, max_its)
            if not self.decode_result:
                if save_llr and len(output) == 174:
                    self.saved_llrs.append((f"{self.pat_name}_LDPC{max_its}", output))
            else:
                self.bits77_int = output

    def _decode_osd(self):
        if not self.decode_result:
            self.decode_notes = f'{self.source}_{self.pat_name}_OSD'
            self.decode_result, self.bits77_int = osd_012(self.llr)

    def _get_llr_grid(self):
        self._dB_to_llr(self.payload_on_search_grid)
        self.source = 'grid'

    def _get_llr_fine(self):
        cycle_spectrum = self.get_cycle_spectrum(need_fresh = self.new_after_subtraction)
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

        ftweaks = range(-50, 51, 8) # 16 steps = 1Hz, 6.25Hz = 100 steps
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
        if self.n_sync_matches > self.n_sync_matches_min:
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
        self.fbins_in_grid = self.search_f0_idx_range[1]  + 8 * self.search_bpt
        self.search_grid = np.ones((self.search_hops_per_grid, self.fbins_in_grid), dtype = np.float32)
        self.samples_per_cycle = int(SAMP_RATE * T_CYC)

        self.search_grid_ptr = int(time_utils.grid_time() * self.search_hops_per_grid / (2 * T_CYC))
        self.last_get_cycle_spectrum = 0
        self.waterfall_data = self._set_waterfall_data()
       
        self.audio_buffer = np.zeros(int(18*SAMP_RATE), dtype=np.float32)
        self.audio_buffer_zero = 0
        self.buffer192000_float32  = np.zeros(192000, dtype=np.float32)
        self._find_input_device(input_device_keywords)
        self._set_pointers(time_utils.grid_time())

        threading.Thread(target = self._load_streamed_audio, daemon=True).start()

    def _set_pointers(self, tg):
        self.search_grid_ptr = int(tg * self.search_hops_per_grid / (2 * T_CYC))
        self.audio_buffer_zero = len(self.audio_buffer) - (self.search_grid_ptr % self.search_hops_per_cycle) * self.samples_perhop

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

    def get_cycle_spectrum(self, need_fresh = False):
        if need_fresh or (time_utils.time() - self.last_get_cycle_spectrum) > 0.1:
            samps_offset = (T_CYC - time_utils.cycle_time()) * SAMP_RATE
            self.buffer192000_float32[:self.samples_per_cycle] = np.roll(self.audio_buffer[-self.samples_per_cycle:], - samps_offset)
            self.cycle_spectrum = np.fft.rfft(self.buffer192000_float32)
        self.last_get_cycle_spectrum = time_utils.time()
        return self.cycle_spectrum

    def get_grid_spectrum(self, grid_ptr):
        samp_n = len(self.audio_buffer) - int(self.samples_perhop * (self.search_grid_ptr - grid_ptr))
        samp_0 = samp_n - self.search_fft_len
        if samp_0 < 0 or samp_n > len(self.audio_buffer):
            return
        np.multiply(self.audio_buffer[samp_0:samp_n], self.search_fft_window, out = self.search_fft_in)
        z = np.fft.rfft(self.search_fft_in)[:self.search_grid.shape[1]]
        self.search_grid[grid_ptr, :] = 20*np.log10(np.abs(z))
            
    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        self.last_audio_buffer_insert = time_utils.time()
        self.audio_buffer_zero = self.audio_buffer_zero - ns
        if self.audio_buffer_zero <= 0:
            self.audio_buffer_zero += self.samples_per_cycle
        self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid
        if self.search_grid_ptr == 0:
            tg = time_utils.grid_time()
            if tg > 0.1:
                self._set_pointers(tg)
        self.get_grid_spectrum(self.search_grid_ptr)
        return (None, pyaudio.paContinue)

#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, input_device_keywords, on_message, sync_score_min = 85, max_cands = 200,
                 on_update = None,
                 search_freq_range = [100, 3000], search_timerange = [-2.5, 3.5], verbose = False,
                 min_cand_separation_Hz = 15, min_sub_separation_Hz = 5, max_subtractions = 30):
        self.audio_in = AudioIn(search_freq_range, input_device_keywords)
        self.on_message = on_message
        self.on_update = on_update
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
        self.cand_serial = 0
        self.init_subtraction()
        self.last_sub_fHz = 0
        self.max_subtractions = max_subtractions
        self.min_cand_separation_Hz = min_cand_separation_Hz
        self.min_sub_separation_Hz = min_sub_separation_Hz
        self.dump_subtraction_info = False

        time_utils.set_cycle_length(T_CYC)
        time_utils.tlog(f"[Receiver] Search hops {self.search_h0_range[0]:3d} to {self.search_h0_range[1]:3d}", verbose = self.verbose)
        time_utils.tlog(f"[Receiver] Start search at hop {self.search_start_hop:3d}", verbose = self.verbose)
        
        time_utils.sleep(0.5)
        threading.Thread(target=self.manage_cycle, daemon=True).start()
        
    def search(self, cyclestart, odd_even, search_f_idxs, cherrypick_neighbouring_candidates = False):
        #print(f"Search cycle starting at {time_utils.format_HMS(cyclestart['t_abs_local_cyc'])}")
        cands = []
        cycle_h0 = odd_even * self.audio_in.search_hops_per_cycle
        hops_per_sig = self.audio_in.search_hps * PAYLOAD_SYMB_IDXS[-1]
        for f0_idx in search_f_idxs:
            self.cand_serial = (self.cand_serial + 1) % 1000
            p = self.audio_in.search_grid[:, f0_idx: f0_idx + 7*self.audio_in.search_bpt]
            origin = {'score':0}
            for h0_idx in range(self.search_h0_range[0], self.search_h0_range[1]):
                score = float(np.dot(p[h0_idx + cycle_h0 + self.base_search_hops + self.audio_in.search_hps, :].ravel(), self.csync_search))
                tsec = h0_idx / (self.audio_in.search_hps * SYM_RATE)
                test_sync = {'h0_idx'   : h0_idx,  'f0_idx':f0_idx,
                             'tsec'     : tsec, 't_abs_local': tsec + cyclestart['t_abs_local_cyc'],
                             'fHz'      : SYM_RATE * f0_idx / self.audio_in.search_bpt,
                             'score'    : score}
                if test_sync['score'] > origin['score']:
                    origin = test_sync
            minscore = self.sync_score_min 
            if origin['score'] > minscore:
                h0, tsec = origin['h0_idx'], origin['tsec']
                origin.update({'cyclestart_string':cyclestart['string'], 'band':self.band, 'odd_even':odd_even})
                search_grid_h0 = cycle_h0 + h0 + self.audio_in.search_hps
                payload_hops = np.array([(search_grid_h0 + self.audio_in.search_hps * s) % self.audio_in.search_hops_per_grid for s in PAYLOAD_SYMB_IDXS])
                payload_hops = np.clip(payload_hops, 0, self.audio_in.search_hops_per_grid)
                payload_freqs = np.array([origin['f0_idx'] + self.audio_in.search_bpt//2 + t * self.audio_in.search_bpt for t in range(8)])
                payload_freqs = np.clip(payload_freqs, 0, self.audio_in.fbins_in_grid)
                payload_on_search_grid = self.audio_in.search_grid[payload_hops,:][:, payload_freqs]
                payload_hop_bounds = [payload_hops[0], payload_hops[-1]]
                costas_hops = 7 * self.audio_in.search_hps
                signal_hop_bounds = [payload_hops[0] - costas_hops, payload_hops[-1] + costas_hops]
                c = Candidate(origin, signal_hop_bounds, payload_hop_bounds, payload_on_search_grid, self.audio_in.get_cycle_spectrum, self.on_message)
                c.serial_id = self.cand_serial
                cands.append(c)
        for c in cands:
            neigh = [cn for cn in cands if np.abs(c.origin['fHz'] - cn.origin['fHz']) < self.min_cand_separation_Hz
                     and c.origin['f0_idx'] != cn.origin['f0_idx']
                     and not cn.subtracted
                     and cn.origin['score'] > 0.75 * c.origin['score']]
            if len(neigh):
                c.neighbours = neigh
                c.has_neighbours = True

        cands_out = []
        for c in cands:
            if not c.has_neighbours or not cherrypick_neighbouring_candidates:
                cands_out.append(c)
            else:                
                idx = np.argmax([c.origin['score'] for c in neigh])
                best_neighbour = neigh[idx]
                if best_neighbour not in cands_out:
                    best_neighbour.has_neighbours = True
                    cands_out.append(best_neighbour)

        #print(','.join([f"{c.origin['fHz']:6.1f}" for c in cands_out]))
        cands_out.sort(key = lambda c: c.origin['score'], reverse = True)
        return cands_out[:self.max_cands]

    def init_subtraction(self, subtraction_filterlen = 2000):
        window = np.cos(np.linspace(0, np.pi/2, subtraction_filterlen))**2
        subtraction_window = np.zeros(192000)
        subtraction_window[:subtraction_filterlen] = window
        subtraction_window[-subtraction_filterlen:] = window[::-1]
        subtraction_window /= np.sum(subtraction_window)
        self.filter_mult = np.fft.fft(subtraction_window)
        self.camp = np.zeros(192000, dtype = np.complex64)

    def subtract_signal(self, c, f_offset = 0, t_offset = 0):
        if np.abs(c.origin['fHz'] - self.last_sub_fHz) < self.min_sub_separation_Hz:
            c.subtracted = True
            print(f"Rejected - too close in frequency to last subtracted signal")
            return
        symbols = symbols = encode_bits77(c.bits77_int)
        if not symbols:
            print(f"Rejected - couldnt generate symbols")
            return
        reference_audio = symbols_to_complex_audio(symbols, f_base = c.origin['fHz'] + f_offset)        
        len_sig = len(reference_audio)
        sig_start_in_audio_buffer = self.audio_in.audio_buffer_zero + int(float(c.origin['tsec']) * SAMP_RATE)
        if sig_start_in_audio_buffer >=0 and sig_start_in_audio_buffer + len_sig < len(self.audio_in.audio_buffer):
            t0 = time_utils.time()
            received_audio = self.audio_in.audio_buffer[sig_start_in_audio_buffer: sig_start_in_audio_buffer + len_sig]
            self.camp[:] = 0
            self.camp[:len_sig] = received_audio * np.conj(reference_audio)
            self.camp = np.fft.fft(self.camp)
            self.camp *= self.filter_mult
            self.camp = np.fft.ifft(self.camp)
            sub = 2*np.real(self.camp[:len_sig] * reference_audio)
            sig_start_in_audio_buffer = self.audio_in.audio_buffer_zero + int(float(c.origin['tsec']) * SAMP_RATE)
            t_sub = time_utils.time()-t0
            if sig_start_in_audio_buffer >=0 and sig_start_in_audio_buffer + len_sig < len(self.audio_in.audio_buffer):
                self.audio_in.audio_buffer[sig_start_in_audio_buffer: sig_start_in_audio_buffer + len_sig] -= sub
                self.last_sub_fHz = c.origin['fHz']
                print(f"Sub at {self.last_sub_fHz:7.2f}Hz {c.origin['tsec']:6.1f}s calcs = {t_sub*1000:6.1f}ms")
                return True
        print(f"Rejected sig length {len_sig} starting point {sig_start_in_audio_buffer} not in range 0 to {len(self.audio_in.audio_buffer) - len_sig}")


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
        n_subtractions = 0
        post_subtraction_successes = 0
        post_subtraction_successes_unique = 0
        new_cands = []
        recovered_callsigns = []
        while True:
            time_utils.sleep(0.1)

            # reset cycle_searched at beginning of cycle
            if self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle < search_grid_ptr_prev:
                cycle_searched = False
            search_grid_ptr_prev = self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle

            # list candidates still to decode, and decode them
            to_decode = [c for c in self.candidates if (not c.decode_result) and (not (c.payload_hop_bounds[0] <= self.audio_in.search_grid_ptr <= c.payload_hop_bounds[1]))]
            if len(to_decode):
                ipasses = [c.ipass for c in to_decode]
                to_decode.sort(key=lambda c: (-c.payload_hop_bounds[0], c.new_after_subtraction, c.llr_sd), reverse=True)
                max_ipass = np.min(ipasses)
                for c in to_decode:
                    c.decode(max_ipass)
                    if c.decode_result is not None:
                        if c.decode_result != 'stop':
                            c.check_and_package(duplicate_filter)
                            if c.new_after_subtraction:
                                post_subtraction_successes += 1
                            if c.post_subtraction_success:
                                for call in c.msg_tuple[:2]:
                                    if not call.startswith('CQ') and not call in recovered_callsigns:
                                        recovered_callsigns.append(call)
                                        with open('recovered_callsigns.txt','a') as f:
                                            f.write(f"{call}\n")
                                post_subtraction_successes_unique += 1

            # subtract candidate signals once audio is clear of the *whole* signal including Costas blocks
            subtracted = []
            ct = time_utils.cycle_time()
            if ct > 13 or ct < 1:
                to_subtract = [c for c in self.candidates if c.msg_tuple and not c.subtracted and not c.new_after_subtraction and
                               not (c.signal_hop_bounds[0] < self.audio_in.search_grid_ptr < c.signal_hop_bounds[1] )]
                to_subtract.sort(key = lambda c: (-c.signal_hop_bounds[0], c.has_neighbours), reverse = True)
                for c in to_subtract:
                    if n_subtractions < self.max_subtractions:
                        c.refine_time_origin()
                        success = self.subtract_signal(c)
                        c.subtracted = True
                        if success:
                            n_subtractions += 1
                            subtracted.append(c)

            if len(subtracted):
                recalc_hops = [10000, -10000]
                for c in subtracted:
                    recalc_hops[0] = recalc_hops[0] if c.signal_hop_bounds[0] > recalc_hops[0] else c.signal_hop_bounds[0]
                    recalc_hops[1] = recalc_hops[1] if c.signal_hop_bounds[1] < recalc_hops[1] else c.signal_hop_bounds[1]
                for grid_ptr in range(recalc_hops[0], recalc_hops[1]):
                    self.audio_in.get_grid_spectrum(grid_ptr)
                for c in subtracted:
                    f0_idx = c.origin['f0_idx']
                    search_f_idxs = range(f0_idx-5, f0_idx+5) # one idx = 6.25 / bpt Hz (3.125 if bpt == 2)
                    potential_new_cands = self.search(cyclestart, c.origin['odd_even'], search_f_idxs)
                    for c in potential_new_cands:
                        if not c in new_cands:
                            new_cands.append(c)        
                for c in new_cands:
                    if not c in self.candidates:
                        c.new_after_subtraction = True
                        self.candidates.append(c)
                        #print(f"New at {c.origin['fHz']:6.1f} {c.origin['tsec']:6.1f}s")
                
            # if cycle not yet searched and search data available, search
            if not cycle_searched and self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle > self.search_start_hop:
                if len(to_decode):
                    time_utils.tlog(f"[Receiver] Warning - {len(to_decode)} candidates ran out of decoding time, ipass = {ipasses}", verbose = True)
                print(f"Previous cycle got {post_subtraction_successes} decodes ({post_subtraction_successes_unique} unique) from {len(new_cands)} candidates added after {n_subtractions} subtractions")
                print(f"Callsigns recovered: {','.join(recovered_callsigns)}")
                odd_even = time_utils.odd_even()
                hstart = self.audio_in.search_grid_ptr
                tstart = time_utils.time()
                time_utils.tlog(f"[Cycle manager] start search at hop {hstart} ({time_utils.cycle_time():6.2f}s)", verbose = True)
                cyclestart = time_utils.cyclestart(time_utils.time())
                search_f_idxs = range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1], 2)
                self.candidates = self.search(cyclestart, odd_even, search_f_idxs)
                neigh_count = len([c for c in self.candidates if c.has_neighbours])
                time_utils.tlog(f"[Cycle manager] New spectrum searched in {time_utils.time() - tstart:6.2f}s -> {len(self.candidates)} candidates ({neigh_count} with neighbours)", verbose = True) 

                n_subtractions = 0
                post_subtraction_successes = 0
                post_subtraction_successes_unique = 0
                new_cands = []
                cycle_searched = True

