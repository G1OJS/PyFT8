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


CAND_END_TAPER = 0.5*(1+np.cos(np.linspace(np.pi,0,100)))
CAND_START_TAPER = 0.5*(1+np.cos(np.linspace(-np.pi,0,100)))
CAND_GRID_79x32 = np.empty((N_SYMS, 32), dtype=np.complex64)
CAND_GRID_7x32 = np.empty((7, 32), dtype=np.complex64)
CSYNC7x7 = np.full((7, 7), -1/6, np.float32)
for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
    CSYNC7x7[sym_idx, tone] = 1.0
    CSYNC49 =  CSYNC7x7.ravel()
CAND_FFT_3200 = np.zeros(3200, dtype = np.complex64)


#============== CANDIDATE ===========================================================


class Candidate:
    def __init__(self, origin, search_grid_bounds, payload_on_search_grid, get_cycle_spectrum, on_message):
        self.origin = origin
        self.search_grid_bounds = search_grid_bounds
        self.payload_on_search_grid = payload_on_search_grid
        self.get_cycle_spectrum = get_cycle_spectrum
        self.on_message = on_message
        self.ch_llrs = []
        self.ch_ldpc_llrs = []
        self.ch_llr_sd = 0
        self.ipass = 0
        self.csync_7x7 = None
        self.symbol_grid = None
        self.decode_result = None
        self.serial_id = None
        self.decode_notes = ''
        self.bits77_int = 0
        self.msg_text = ''

    def check_and_package(self, duplicate_filter):
        self.msg_text = ' '.join(self.decode_result)
        key = self.origin['cyclestart_string'] + self.msg_text
        if (key not in duplicate_filter):
            duplicate_filter.add(key)
            o = self.origin
            decode_notes = self.decode_notes
            tsec, fHz = o['tsec'], o['fHz']
            their_snr = f"{self.snr:+03d}"
            all_txt_format = f"{o['cyclestart_string']} {their_snr} {(tsec-0.6):4.1f} {fHz:4.0f} ~ {self.msg_text}"
            message = { "band":o['band'], "tsec":tsec, "fHz":fHz, "msg_tuple":self.decode_result,
                        "their_snr": their_snr, "their_tx_cycle":o['odd_even'],
                        "all_txt_format": all_txt_format, 'cyclestart_string':o['cyclestart_string'],
                        "decode_completed": time_utils.time(), 'decode_notes':decode_notes}
            self.on_message(message)
        self.decode_result = 'stop'

    def decode(self, current_max_ipass):
        time_utils.sleep(0)
        if (self.ipass <= current_max_ipass) and (self.decode_result != 'stop'):

            if self.ipass == 0:
                self._get_ch_llrs_from_grid()

            if self.ipass == 1:
                for llr in self.ch_llrs:
                    self._decode_good91(llr)
                    if self.decode_result: break

            if self.ipass == 2:
                for llr in self.ch_llrs:                    
                    self._decode_ldpc(llr, 35, 5, False)
                    if self.decode_result: break

            if self.ipass == 3:
                self._get_ch_llrs_from_spectrum()

            if self.ipass == 4:
                for llr in self.ch_llrs:
                    if llr[0] != 'grid':
                        self._decode_good91(llr)
                        if self.decode_result: break

            if self.ipass == 5:
                for llr in self.ch_llrs:
                    if llr[0] != 'grid':
                        self._decode_ldpc(llr, 35, 5, False)
                        if self.decode_result: break

            if self.ipass == 6:
                for llr in self.ch_llrs:
                    self._decode_osd(llr, 2)
                    if self.decode_result: break

            if self.ipass == 7:
                for llr in self.ch_llrs:
                    self._decode_ldpc(llr, 90, 20, True)
                    if self.decode_result: break

            if self.ipass == 8:
                for llr in self.ch_ldpc_llrs:
                    self._decode_osd(llr, 0)
                    if self.decode_result: break

            if self.ipass == 9:
                self.decode_result = 'stop'
            
            self.ipass +=1

    def _set_AP(self, source, llr):
        llr0 = llr.copy()
        self.ch_llrs.append((source + '_CH', llr))
        """
        llr[:29] = -5
        llr[26] = 5
        llr[74:76] = -5
        llr[76] = 5
        llr[57:59] = -5
        self.ch_llrs.append((source + '_CQ', llr))
        """
        llr = llr0.copy()
        llr[58] = -5
        llr[59:65] = 5
        llr[65] = -5
        llr[69] = 5
        llr[70] = -5
        llr[74:76] = -5
        self.ch_llrs.append((source + '_RR', llr))
        
        
    def _decode_good91(self, pat_llr):
        self.decode_result, self.bits77_int = crc_unpack91(pat_llr[1][:91])
        if self.decode_result:
            self.decode_notes = f"{pat_llr[0]}_GOOD91"
                
    def _decode_ldpc(self, pat_llr, max_nc0, max_its, save_llr):
        self.decode_result, self.n_its, output = ldpc_decode(pat_llr[1], max_nc0, max_its)
        notes = f"{pat_llr[0]}_LDPC({max_its})"
        if not self.decode_result:
            if save_llr and len(output) == 174:
                self.ch_ldpc_llrs.append((notes, output))
        else:
            self.bits77_int = output
            self.decode_notes = notes

    def _decode_osd(self, pat_llr, maxord):
        self.decode_result, self.bits77_int, osd_order_success = osd_012(pat_llr[1], maxord, singleflips = 30, doubleflips = 2)
        if self.decode_result:
            self.decode_notes = f"{pat_llr[0]}_OSD({osd_order_success})"
            
    def _power_to_llr(self, power_grid):
        p = power_grid
        llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
        llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
        llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
        llr = np.column_stack((llra, llrb, llrc)).ravel()
        mean = np.mean(llr)
        var = np.mean(llr*llr) - mean*mean
        self.ch_llr_sd = np.sqrt(var)
        if self.ch_llr_sd < 0.5:
            self.decode_result = 'stop'
        else:
            return 2.83 * llr / self.ch_llr_sd

    def _get_ch_llrs_from_grid(self):
        p = self.payload_on_search_grid
        self.snr = np.clip(int(np.max(p) - np.min(p) - 58), -24, 24)
        llr = self._power_to_llr(p) # called with dB not power
        if llr is not None:
            self._set_AP('grid', llr)

    def _get_ch_llrs_from_spectrum(self):
        # first part similar to calls to sync8d except latter scores costas in time domain
        # meaning that df can be applied as a linear phase shift
        # (could try this here by calculating zsig only once and applying shifts the same way)
        self.cycle_spectrum = self.get_cycle_spectrum()
        fb0 = int(self.origin['fHz'] * 192000 / SAMP_RATE )
        tb0 = int(self.origin['tsec'] / 0.005)
        fb, tb = fb0, tb0
        
        self._set_fb(fb)
        refine = range(-10, 10, 2) # 32 steps = 1 symbol
        scores = [self._symbol_grid_score(tb + r) for r in refine]
        tb += refine[np.argmax(scores)]
        
        refine = range(-45, 46, 4) # 6.25Hz = 100 steps, 2.5Hz = 40 steps
        scores = []
        for r in refine:
            self._set_fb(fb + r)
            scores.append(self._symbol_grid_score(tb))
        fb += refine[np.argmax(scores)]
        self._set_fb(fb)
           
        self.symbol_grid = self._symbol_grid(tb)
        
        if self._count_costas_maxima() < 7:
            self.decode_result = 'stop'
            return
        
        idf, idt = fb - fb0, tb - tb0
        self.origin.update({'tsec': float(self.origin['tsec'] + idt / 200),
                            'fHz':float(self.origin['fHz'] + idf / 16) })
        llr = self._power_to_llr(self.symbol_grid[PAYLOAD_SYMB_IDXS, :])
        if llr is not None:
            self._set_AP('fine', llr)


 #       with open('tweaks.txt','a') as f:
 #           f.write(f"{idf}, {idt}\n")

    def _count_costas_maxima(self):
        costas_symbol_grid = self.symbol_grid[COSTAS_SYMB_IDXS, :]
        costas_delta_freqs = np.argmax(costas_symbol_grid, axis = 1) - (COSTAS * 3)
        return len([df for df in costas_delta_freqs if df == 0])
        
    def _set_fb(self, fb):
        global CAND_FFT_3200
        if fb >= 150:
            CAND_FFT_3200[:] = 0
            CAND_FFT_3200[:850] = self.cycle_spectrum[fb:fb+850]
            CAND_FFT_3200[750:850] *= CAND_END_TAPER
            CAND_FFT_3200[3050:] = self.cycle_spectrum[fb-150:fb]
            CAND_FFT_3200[3050:3150] *= CAND_START_TAPER
            self.zsig = np.fft.ifft(CAND_FFT_3200)

    def _symbol_grid(self, tb):
        idx = tb + np.arange(N_SYMS)*32
        idx = np.clip(idx, 0, 3200-32)
        for j, i0 in enumerate(idx):
            CAND_GRID_79x32[j,:] = self.zsig[i0:i0+32]
        return np.abs(np.fft.fft(CAND_GRID_79x32, axis=1)[:, :8])

    def _symbol_grid_score(self, tb):
        idx = tb + (36+np.arange(7))*32
        for j, i0 in enumerate(idx):
            CAND_GRID_7x32[j,:] = self.zsig[i0:i0+32]
        costas_powers = np.abs(np.fft.fft(CAND_GRID_7x32, axis=1)[:, :7])
        return float(np.dot(costas_powers.ravel(), CSYNC49))

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
        #if (time_utils.time() - self.last_get_cycle_spectrum) < 0.05:
        #    return
        self.last_get_cycle_spectrum = time_utils.time()
        samps_offset = (T_CYC - time_utils.cycle_time()) * SAMP_RATE
        self.fft1_buffer[:self.samples_per_cycle] = np.roll(self.audio_buffer[-self.samples_per_cycle:], - samps_offset)
        self.cycle_spectrum = np.fft.rfft(self.fft1_buffer)
        return self.cycle_spectrum
            
    def get_grid_spectrum(self, grid_ptr):
        np.multiply(self.audio_buffer[-self.search_fft_len:], self.search_fft_window, out = self.search_fft_in)
        z = np.fft.rfft(self.search_fft_in)[:self.search_grid.shape[1]]
        self.search_grid[grid_ptr, :] = 20*np.log10(np.abs(z)+1e-12)        
        
    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16)#.astype(np.float32)
        n = len(samples)
        self.audio_buffer[:-n] = self.audio_buffer[n:]
        self.audio_buffer[-n:] = samples
        self.search_grid_ptr = (self.search_grid_ptr + 1) % self.search_hops_per_grid
        if self.search_grid_ptr == 0:
            tg = time_utils.grid_time()
            if tg > 0.1:
                self.search_grid_ptr = int(tg * self.search_hops_per_grid / (2 * T_CYC))
        self.get_grid_spectrum(self.search_grid_ptr)
        return (None, pyaudio.paContinue)

#============== RECEIVER ===========================================================
        
class Receiver():
    def __init__(self, input_device_keywords, on_message, sync_score_min = 95, max_cands = 250,
                 search_freq_range = [100, 3000], search_timerange = [-2.5, 3.5], verbose = False):
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
        self.cand_serial = 0
        
        time_utils.set_cycle_length(T_CYC)
        time_utils.tlog(f"[Receiver] Search hops {self.search_h0_range[0]:3d} to {self.search_h0_range[1]:3d}", verbose = self.verbose)
        time_utils.tlog(f"[Receiver] Start search at hop {self.search_start_hop:3d}", verbose = self.verbose)
        
        time_utils.sleep(0.5)
        threading.Thread(target=self.manage_cycle, daemon=True).start()
        
    def search(self, cyclestart_string, odd_even, search_f_idxs, ignore_sync_score_min = False):
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
            minscore = self.sync_score_min if not ignore_sync_score_min else 0
            if origin['score'] > minscore:
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
                to_decode.sort(key=lambda c: c.ch_llr_sd, reverse=True)
                max_ipass = 10 + np.min(ipasses)
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
                search_f_idxs = range(self.audio_in.search_f0_idx_range[0], self.audio_in.search_f0_idx_range[1], 1)
                odd_even = time_utils.odd_even()
                self.candidates = self.search(cyclestart_string, odd_even, search_f_idxs)
                cycle_searched = True
                time_utils.tlog(f"[Cycle manager] New spectrum searched in {time_utils.time() - tstart:6.2f}s -> {len(self.candidates)} candidates", verbose = True) 

