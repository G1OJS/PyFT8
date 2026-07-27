import threading
import numpy as np
import pyaudio
from PyFT8.time_utils import time_utils
from PyFT8.decoders import ldpc_decode, osd_decode, crc_unpack91

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
    def __init__(self, origin, search_grid_bounds, payload_on_search_grid, get_full_audio, process_message, llr_sd_min = 5):
        self.origin = origin
        self.search_grid_bounds = search_grid_bounds
        self.payload_on_search_grid = payload_on_search_grid
        self.get_full_audio = get_full_audio
        self.process_message = process_message
        self.llr_sd_min = llr_sd_min
        self.csync_7x7 = None
        self.signal_grid = None
        self.fft2_len = 3200
        self.reused_spectrum_array = np.zeros(self.fft2_len, dtype = np.complex64)
        self.serial_id = None
        self.decode_notes = ''
        self.msg_checked = False

    def _check_msg_and_package(self, duplicate_filter):
        if self.decode_result:
            key = self.origin['cyclestart_string'] + ''.join(self.decode_result)
            if (key not in duplicate_filter):
                duplicate_filter.add(key)
                o = self.origin
                decode_notes = self.decode_notes
                tsec, fHz = o['tsec'], o['fHz']
                their_snr = f"{self.snr:+03d}"
                msg_text = ' '.join(self.decode_result)
                all_txt_format = f"{o['cyclestart_string']} {their_snr} {(tsec-0.5):4.1f} {fHz:4.0f} ~ {msg_text}"
                message = {"band":o['band'], "tsec":tsec, "fHz":fHz, "msg_tuple":self.decode_result, "their_snr": their_snr, "their_tx_cycle":o['odd_even'],
                        "all_txt_format": all_txt_format,
                        "decode_completed": time_utils.time(),  'serial_id': self.serial_id, 'decode_notes':decode_notes}
                self.on_message(message)
            self.decode_result = False

    def decode(self, duplicate_filter, current_max_ipass, all_audio_spectrum):
        time_utils.sleep(0)
        if self.ipass <= current_max_ipass:
                        
            if self.ipass == 0:
                source = 'grid          '
                self.llr, self.llr_sd, self.snr = self.dB_to_llr(self.payload_on_search_grid)
                if self.llr_sd > self.llr_sd_min:
                    self._decode_good91(source)
                    self._decode_ldpc_AP(source, [1, 0], 35, 5, False) # try CQ pattern first
            
            source = f'fine {self.tweaks}'
            if self.ipass == 1:
                self.all_audio_spectrum = self.get_full_audio()
                self.n_sync_matches, self.llr, self.llr_sd, self.snr = self._get_llr_fine(self.all_audio_spectrum)
                if self.n_sync_matches < 6:
                    self.decode_completed = True
                    return
                self._decode_good91(source)       
            if self.ipass == 2:
                self._decode_ldpc_AP(source, [0], 35, 5, False)
            if self.ipass == 3:
                self._decode_ldpc_AP(source, [0,1,2,3,4], 55, 25, True)
            if self.ipass == 4: # no decode, just prep
                self.rel_ord = np.argsort(np.abs(self.llr))[::-1]
                self.saved_llrs = [('demap', self.llr)] + self.saved_llrs
            i_saved = self.ipass - 5
            if len(self.saved_llrs) > i_saved >= 0:
                self._decode_osd(source, self.saved_llrs[i_saved])
            if self.decode_result or i_saved == len(self.saved_llrs):
                self.decode_completed = True
            self.ipass +=1

    def _decode_good91(self, source):
        if not self.decode_result:
            self.decode_notes = f'{source} GOOD91'
            self.decode_result = crc_unpack91(self.llr[:91])
                
    def _decode_ldpc_AP(self, source, ap_indexes, max_nc0, max_its, save_llr):
        if not self.decode_result:
            self.saved_llrs = []
            for ipat in ap_indexes:
                self.decode_notes = f'{source} LDPC {pat_name}'
                pat_name, b0, ap_pattern = ap_patterns[ipat]
                llr = self.llr.copy()
                for b, bval in enumerate(ap_pattern):
                    llr[b0 + b] = (bval*2-1) * 5
                if pat_name == 'CQ':
                    llr[74:76] = -5
                    llr[76] = 5
                   # llr[57:59] = -5
                self.decode_result, self.n_its, output_llr = ldpc_decode(llr, max_nc0, max_its)
                if save_llr and not self.decode_result and not len(output_llr) == 174:
                    self.saved_llrs.append((pat_name, output_llr))
                if self.decode_result:
                    break
                
    def _decode_osd(self, source, patname_llr):
        if not self.decode_result:
            pat_name, llr = patname_llr
            self.decode_notes = f'{source} OSD {pat_name}'
            self.decode_result = osd_decode(llr, self.rel_ord)

    def _get_llr_fine(self, all_audio_spectrum):
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
            self._get_signal_grid_fine(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ttweak = ttweaks[np.argmax(scores)]

        ftweaks = range(-50, 51, 16) # 16 steps = 1Hz, 6.25Hz = 100 steps
        scores = []
        for ftweak in ftweaks:
            self._get_signal_grid_fine(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
            scores.append(self.score)
        ftweak = ftweaks[np.argmax(scores)]

        self._get_signal_grid_fine(all_audio_spectrum, fb_0+ftweak, fb_bot+ftweak, fb_top+ftweak, tb_0+ttweak)
        self.tweaks = f"t:{ttweak:+03d} f:{ftweak:+03d}"

        costas_abs_grid = self.signal_grid[COSTAS_SYMB_IDXS, :]
        ccheck = np.argmax(costas_abs_grid, axis = 1) - (COSTAS * 3)
        n_sync_matches = len([c for c in ccheck if c == 0])
        if n_sync_matches > 6:
            self.origin.update({'tsec': float(self.origin['tsec'] + ttweak / 200),
                                'fHz':float(self.origin['fHz'] + ftweak / 16) })
            payload_dB_grid = 20*np.log10(self.signal_grid[PAYLOAD_SYMB_IDXS, :])
            llr, llr_sd, snr = self._dB_to_llr(payload_dB_grid)
        else:
            llr, llr_sd, snr = [], 0, -30

        return n_sync_matches, llr, llr_sd, snr

    def _get_signal_grid_fine(self, all_audio_spectrum, fb_0, fb_bot, fb_top, tb_0): 

        fft1_len = len(all_audio_spectrum)

        # downsample to 32 samples per symbol / 200 samples per sec
        self.reused_spectrum_array[:(fb_top - fb_0)] = all_audio_spectrum[fb_0:fb_top]
        self.reused_spectrum_array[-(fb_0-fb_bot):] = all_audio_spectrum[fb_bot:fb_0]
        candidate_zsig = np.fft.ifft(self.reused_spectrum_array)

        # get candidate symbol spectra x79 with df = 1 tone spacing
        symbols = np.empty((N_SYMS, 32), dtype=np.complex64)
        idx = tb_0 + np.arange(N_SYMS)*32
        idx = np.clip(idx, 0, len(candidate_zsig)-32)
        symbols = np.empty((N_SYMS,32), dtype=np.complex64)
        for j, i0 in enumerate(idx):
            symbols[j,:] = candidate_zsig[i0:i0+32]
        self.signal_grid = np.abs(np.fft.fft(symbols, axis=1)[:, :8])

        if not self.csync_7x7:
            csync = np.full((7, 7), -1/6, np.float32)
            for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
                csync[sym_idx, tone] = 1.0
            self.csync_7x7 =  csync.ravel()
        self.score = float(np.dot(self.signal_grid[36:43, :7].ravel(), self.csync_7x7))

    def _dB_to_llr(self, payload_dB_grid):
        p = payload_dB_grid 
        snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        mean = np.mean(llr)
        var = np.mean(llr*llr) - mean*mean
        rootvar = np.sqrt(var)
        return 2.83 * llr / rootvar, rootvar, snr

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

        self.cycle_audio_buffer_ptr = 0
        self.search_grid_ptr = 0
        self.search_grid_ptr_at_last_spectrum_calc = 0
        self.waterfall_data = self._set_waterfall_data()
        self.search_audio_buffer = np.zeros(self.search_fft_len, dtype=np.float32)
        self.search_fft_in = np.zeros(self.search_fft_len, dtype=np.float32)        
        self.cycle_audio_buffer = np.zeros(192000, dtype=np.float32)
        self.adj, self.cycle_audio_buffer_ptr_prev, self.t_prev = 1.0, -1, None
        self._set_pointers()
        self._find_input_device(input_device_keywords)

        threading.Thread(target = self._load_streamed_audio, daemon=True).start()
        threading.Thread(target = self._manage_audio_in_cycle, daemon=True).start()

    def get_full_audio_spectrum(self):
        if np.abs(self.search_grid_ptr - self.search_grid_ptr_at_last_spectrum_calc) > 0 : 
            self.search_grid_ptr_at_last_spectrum_calc = self.search_grid_ptr
            self.all_audio_spectrum = np.fft.rfft(self.cycle_audio_buffer) # only calc full spectrum if more samples received
        return self.all_audio_spectrum

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

#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, input_device_keywords, on_message, sync_score_min = 100, max_cands = 1000,
                 search_freq_range = [100, 3000], search_timerange = [-2, 5], verbose = False):
        self.audio_in = AudioIn(search_freq_range, input_device_keywords)
        self.on_message = on_message
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
        search_f_idxs = range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1], 2)
        for cand_serial, f0_idx in enumerate(search_f_idxs):
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
                hops = np.array([(search_grid_h0 + self.audio_in.search_hps * s)% self.audio_in.search_hops_per_grid for s in PAYLOAD_SYMB_IDXS])
                freqs = np.array([origin['f0_idx'] + self.audio_in.search_bpt//2 + t * self.audio_in.search_bpt for t in range(8)])
                payload_on_search_grid = self.audio_in.search_grid[hops,:][:, freqs]
                c = Candidate(origin, [search_grid_h0, search_grid_hn], payload_on_search_grid, self.audio_in.get_full_audio_spectrum, self.on_message)
                c.serial_id = cand_serial
                cands.append(c)
        cands.sort(key = lambda c: c.origin['score'], reverse = True)
        self.candidates = cands[:self.max_cands]

    def set_band(self, band):
        self.band = band

    def manage_cycle(self):
        dashes = "======================================================"
        duplicate_filter = set()
        time_utils.tlog(f"[Receiver] running", verbose = self.verbose)
        ptr_at_last_spectrum_calc = -1
        search_grid_ptr_prev = 0
        cycle_searched = False
        end_decoding_message_printed = False
        all_audio_spectrum = None
        while True:
            time_utils.sleep(0.1)

            # reset cycle_searched at beginning of cycle
            if self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle < search_grid_ptr_prev:
                cycle_searched = False
            search_grid_ptr_prev = self.audio_in.search_grid_ptr % self.audio_in.search_hops_per_cycle

            # list candidates still to decode, and decode them
            to_decode = [c for c in self.candidates if not c.decode_completed]
            if len(to_decode):
                to_decode.sort(key=lambda c: c.llr_sd, reverse=True)
                max_ipass = 1 + np.min([c.ipass for c in to_decode])
                for c in to_decode:
                    if not (c.search_grid_bounds[0] <= self.audio_in.search_grid_ptr <= c.search_grid_bounds[1]):
                        c.decode(duplicate_filter, max_ipass)

            # print decode completed message
            if len(to_decode) == 0:
                if not end_decoding_message_printed:
                    tnow = time_utils.cycle_time()
                    time_utils.tlog(f"[Receiver] Finished decoding at t={tnow:6.2f}s", verbose = True)
                    end_decoding_message_printed = True

            # if cycle not yet searched and search data available, search
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

