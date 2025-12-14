import threading
import numpy as np
from .timers import *
from .audio import find_device, AudioIn
from .FT8_demodulator import FT8Demodulator
from .decode174_91_v5_5 import LDPC174_91
from .FT8_unpack import FT8_unpack
import pyaudio
import queue
import wave

class Spectrum:
    def __init__(self, demodspec):
        self.sigspec = demodspec.sigspec
        self.hops_persymb = demodspec.hops_persymb
        self.fbins_pertone = demodspec.fbins_pertone
        self.max_freq = 3500 
        self.dt = demodspec.samples_perhop / demodspec.sample_rate
        self.FFT_len = int(demodspec.fbins_pertone * demodspec.sample_rate // self.sigspec.symbols_persec)
        FFT_out_len = int(self.FFT_len/2) + 1
        fmax_fft = demodspec.sample_rate/2
        self.nFreqs = int(FFT_out_len * self.max_freq / fmax_fft)
        self.df = self.max_freq / self.nFreqs
        self.hops_percycle = int(self.sigspec.cycle_seconds * self.sigspec.symbols_persec * demodspec.hops_persymb)
        self.candidate_size = (self.sigspec.num_symbols * demodspec.hops_persymb,
                               self.sigspec.tones_persymb * demodspec.fbins_pertone)
        
        self._csync = np.full((self.sigspec.costas_len, self.candidate_size[1]), -1/(self.sigspec.costas_len-1), np.float32)
        for sym_idx, tone in enumerate(self.sigspec.costas):
            fbins = range(tone* demodspec.fbins_pertone, (tone+1) * demodspec.fbins_pertone)
            self._csync[sym_idx, fbins] = 1.0
            self._csync[sym_idx, self.sigspec.costas_len*demodspec.fbins_pertone:] = 0
        self.hop_idxs_Costas =  np.arange(self.sigspec.costas_len) * demodspec.hops_persymb

        self.fine_grid_complex = np.zeros((2 * self.hops_percycle, self.nFreqs), dtype = np.complex64)
        self.fine_grid_pointer = 0
        self.occupancy = np.zeros(self.nFreqs)


class Cycle_manager():
    def __init__(self, sigspec, onSuccessfulDecode, onOccupancy, audio_in_wav = None, input_device_keywords = None,
                 max_iters = 90, max_stall = 8, max_ncheck = 30, timeout = 1,
                 sync_score_thresh = 3, max_cycles = 5000, thread_PyFT8_decode_manager = False, return_candidate = False):
        self.running = True
        self.cands_list = []
        self.return_candidate = return_candidate
        self.sigspec = sigspec
        self.max_ncheck = max_ncheck
        self.demod = FT8Demodulator(sigspec)
        self.spectrum = Spectrum(self.demod)
        self.spectrum_lock = threading.Lock()
        self.input_device_idx = find_device(input_device_keywords)
        self.audio_in = AudioIn(self, np.kaiser(self.spectrum.FFT_len, 20))
        self.ldpc = LDPC174_91(max_iters, max_stall, max_ncheck, timeout)

        self.audio_in_wav = audio_in_wav
        self.max_cycles = max_cycles
        self.cycle_countdown = max_cycles
        self.cyclestart_str = None
        self.prev_cycle_time = 1e40
        n_hops_sync_band  = self.demod.slack_hops + np.max(self.spectrum.hop_idxs_Costas)
        self.t_search = n_hops_sync_band * self.spectrum.dt

        self.cands_list = []
        self.cands_list_lock = threading.Lock()
        self.sync_score_thresh = sync_score_thresh
        self.started_ldpc = False
        self.old_cands_list = []
        self.cands_removed = None
        self.min_ncheck_removed = None
        self.duplicate_filter = set()
        self.total_ldpc_time = 0

        self.onSuccessfulDecode = onSuccessfulDecode
        self.onOccupancy = onOccupancy

        threading.Thread(target=self.threaded_spectrum_tasks, daemon=True).start()
        if(thread_PyFT8_decode_manager): threading.Thread(target=self.PyFT8_decode_manager, daemon=True).start()

        with open("timings.log","w") as f:
            f.write("cycle,tcycle,epoch,id,sync_returned,demap_requested,demap_returned,"
                    +"ncheck_initial,ldpc_requested,ldpc_returned,message_decoded,"
                    +"ldpc_frac_time\n")

    def output_timings(self):
        print("Output timings")
        def t(et,cb):
            return f"{et - cb :6.2f}" if et else None
        ldpc_frac_time = self.total_ldpc_time / (tnow()-self.decoder_start_time)
        for c in self.old_cands_list:
            cb = c.cycle_start
            timedLog(f"{c.id},{t(c.sync_returned,cb)},{t(c.demap_requested,cb)},{t(c.demap_returned,cb)},"
                           +f"{c.ncheck_initial},{t(c.ldpc_requested,cb)},"
                           +f"{t(c.ldpc_returned,cb)},{t(c.message_decoded,cb)},{ldpc_frac_time}", logfile = 'timings.log', silent = True)

    def threaded_spectrum_tasks(self):
        timedLog("Rollover manager waiting for end of partial cycle")
        while (tnow() % self.demod.sigspec.cycle_seconds) < self.demod.sigspec.cycle_seconds  - 0.1 :
            sleep(0.01)
        threading.Thread(target = self.audio_in.stream, args=(self.audio_in_wav,), daemon=True).start()
        cycle_searched = False
        minimised_queue = False
        metric_headers = False
        while self.running:
            sleep(0.25)
            cycle_time = tnow() % self.demod.sigspec.cycle_seconds 
            if (cycle_time < self.prev_cycle_time): 
                if not self.cycle_countdown:
                    self.running = False
                    break
                dumped_stats = False
                self.spectrum.fine_grid_pointer = 0
                print()
                timedLog(f"Cycle rollover {cycle_time:.2f}", logfile='waitlist.log' )
                self.cycle_countdown -=1
                self.cyclestart_str = cyclestart_str()
                cycle_searched = False
                self.started_ldpc = False
            self.prev_cycle_time = cycle_time

            # remove old candidates and dump summary stats for cycle (for first 10 cycles)
            if (cycle_time > self.t_search -1 and not dumped_stats):
                dumped_stats = True                    
                self.old_cands_list = self.cands_list
                self.cands_list =[c for c in self.cands_list if c.ldpc_requested and not c.ldpc_returned]
                self.cands_removed = [c for c in self.old_cands_list if c not in self.cands_list]
                if(self.cycle_countdown > self.max_cycles - 10):
                    self.output_timings()

            # search for candidates (only once per cycle)
            if (cycle_time > self.t_search and not cycle_searched):
                cycle_searched = True
                timedLog(f"Search spectrum ...")
                idx_n = self.spectrum.fine_grid_pointer
                idx_0 = idx_n - self.demod.slack_hops - self.sigspec.costas_len * self.demod.hops_persymb
                
                with self.spectrum_lock:
                    self.spectrum.sync_search_band = self.spectrum.fine_grid_complex[idx_0:idx_n,:].copy()
                cands = self.demod.find_syncs(self.spectrum, self.sync_score_thresh)
                with self.cands_list_lock:
                    self.cands_list = self.cands_list + cands

                timedLog(f"Spectrum searched -> {len(self.cands_list)} candidates")
                if(self.onOccupancy): self.onOccupancy(self.spectrum.occupancy, self.spectrum.df)

            # find new candidates that can have spectrum filled, and demap them:
            if(cycle_time > 10):
                with self.cands_list_lock:
                    to_decode = [c for c in self.cands_list if (self.spectrum.fine_grid_pointer > c.last_data_hop
                                  or (self.cyclestart_str != c.cyclestart_str and self.spectrum.fine_grid_pointer +  self.spectrum.hops_percycle > c.last_data_hop) )]
                for c in to_decode:
                    if not c.demap_requested:
                        c.demap_requested = tnow()
                        with self.spectrum_lock:
                            c.synced_grid_complex = self.spectrum.fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0],
                                                                                    c.origin[1]:c.origin[1]+c.size[1]].copy()
                        c.llr, c.llr_sd, c.snr = self.demod.demap_candidate(c)
                        c.ncheck_initial = self.ldpc.fast_ncheck(c.llr)
                        c.demap_returned = tnow()  

    def PyFT8_decode_manager(self):
        self.decoder_start_time = tnow()
        while self.running:    
            sleep(0.1)
            to_decode = [c for c in self.cands_list if not c.ldpc_requested and c.ncheck_initial <= self.max_ncheck]
            if(to_decode):
                this_cycle_start = np.max([c.cycle_start for c in to_decode])
                to_decode.sort(key = lambda c: c.ncheck_initial)            
                for c in to_decode[:10]:
                    c.ldpc_requested = tnow()
                    ldpc_result = self.ldpc.decode(c)
                    c.payload_bits, c.n_its, c.ncheck_initial = ldpc_result['payload_bits'], ldpc_result['n_its'], ldpc_result['ncheck_initial']
                    c.ldpc_returned = tnow()
                    self.total_ldpc_time +=c.ldpc_returned - c.ldpc_requested
                    message_parts = FT8_unpack(c.payload_bits)
                    if(message_parts):
                        key = c.cyclestart_str+" "+' '.join(message_parts)
                        if(not key in self.duplicate_filter):
                            self.duplicate_filter.add(key)
                            freq_str = f"{c.origin[3]:4.0f}"
                            time_str = f"{c.origin[2]:4.1f}"
                            c.decode_dict = {
                                'cyclestart_str':c.cyclestart_str, 'decoder':'PyFT8', 'freq':float(freq_str), 't_decode':tnow(), 
                                'dt':float(time_str), 't0_idx':c.origin[0],'f0_idx':c.origin[1], 
                                'call_a':message_parts[0], 'call_b':message_parts[1], 'grid_rpt':message_parts[2],
                                'sync_score':c.sync_score, 'snr':c.snr, 'llr_sd':c.llr_sd, 'n_its':c.n_its, 'ncheck_initial':c.ncheck_initial
                                }
                            c.message_decoded = tnow()
                            self.onSuccessfulDecode(c if self.return_candidate else c.decode_dict)  
                           




                 
