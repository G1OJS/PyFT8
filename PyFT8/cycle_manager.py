import threading
import numpy as np
import time
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.candidate import Candidate
from PyFT8.spectrum import Spectrum
from PyFT8.audio import find_device
from PyFT8.time_utils import global_time_utils
import os

class Cycle_manager():
    def __init__(self, sigspec, on_decode, run = True, on_occupancy = None, wav_input = None,
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200, 3100], verbose = False):
        self.spectrum = Spectrum(sigspec, 12000, freq_range[1], 4, 2)
        self.verbose = verbose
        self.f0_idxs = range(int(freq_range[0]/self.spectrum.df),
                        min(self.spectrum.nFreqs - self.spectrum.fbins_per_signal, int(freq_range[1]/self.spectrum.df)))
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.on_decode = on_decode
        self.wav_input = wav_input
        self.on_occupancy = on_occupancy
        if(self.output_device_idx):
            from PyFT8.audio import AudioOut
            self.audio_out = AudioOut
        self.audio_started = False
        if(run):
            threading.Thread(target=self.manage_cycle, daemon=True).start()

    def analyse_hoptimes(self):
        if(self.verbose):
            if not any(self.spectrum.audio_in.hoptimes): return
            diffs = np.ediff1d(self.spectrum.audio_in.hoptimes)
            m = 1000*np.mean(diffs)
            s = 1000*np.std(diffs)
            pc = int(100*s /(1000/self.spectrum.sigspec.symbols_persec) )
            global_time_utils.tlog(f"[Cycle manager] Hop timings: mean = {m:.2f}ms, sd = {s:.2f}ms ({pc:5.1f}% symbol)")

    def manage_cycle(self):
        cycle_searched_1, cycle_searched_2 = False, False
        cycle_time_prev = 0
        candidates = []
        block2_cands = []
        duplicate_filter = set()
        if(self.wav_input is None):
            tstart = 0
            delay = self.spectrum.sigspec.cycle_seconds - cycle_time()
            tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)\n")
        else:
            global_time_utils.set_time_offset(time.time()+1)
            threading.Thread(target=self.spectrum.audio_in.load_wav, args = (self.wav_input, self.spectrum.dt, ),  daemon=True).start()

        def summarise_cycle():
            if(self.verbose):
                with_message = [c for c in candidates if c.msg]
                failed = [c for c in candidates if c.decode_completed and not c.msg]
                unprocessed = [c for c in candidates if not "#" in c.decode_path]
                ns, nf, nu = len(with_message), len(failed), len(unprocessed)
                global_time_utils.tlog(f"[Cycle manager] Last cycle had {ns} decodes, {nf} failures and {nu} unprocessed (total = {ns+nf+nu})")   

        while not self.spectrum.audio_in.wav_finished:
            time.sleep(0.001)
            ct = global_time_utils.cycle_time() 
            rollover = ct < cycle_time_prev 
            cycle_time_prev = ct

            if(rollover):
                if(self.verbose):
                    global_time_utils.tlog("======================================================")
                    global_time_utils.tlog(f"[Cycle manager] rollover detected at {global_time_utils.cycle_time():.2f}", verbose = self.verbose)
                cycle_searched_1, cycle_searched_2 = False, False
                self.check_for_tx()
                self.spectrum.audio_in.main_ptr = 0
                self.analyse_hoptimes()
                self.spectrum.audio_in.hoptimes = []
                if not self.audio_started and not self.wav_input:
                    self.audio_started = True
                    self.spectrum.audio_in.start_live(self.input_device_idx)

            if (self.spectrum.audio_in.main_ptr > self.spectrum.h_search1 and not cycle_searched_1):
                cycle_searched_1 = True
                summarise_cycle()
                global_time_utils.tlog(f"[Cycle manager] start first search at hop { self.spectrum.audio_in.main_ptr}", verbose = self.verbose)
                candidates = self.spectrum.search(self.f0_idxs, global_time_utils.cyclestart_str(time.time()), 0)
                global_time_utils.tlog(f"[Cycle manager] New spectrum searched -> {len(candidates)} candidates", verbose = self.verbose) 
                if(self.on_occupancy):
                    self.on_occupancy(self.spectrum.occupancy, self.spectrum.df)
                    
            if (self.spectrum.audio_in.main_ptr > self.spectrum.h_search2 and not cycle_searched_2):
                cycle_searched_2 = True
                global_time_utils.tlog(f"[Cycle manager] start second search at hop { self.spectrum.audio_in.main_ptr}", verbose = self.verbose)
                block2_cands = self.spectrum.search(self.f0_idxs, global_time_utils.cyclestart_str(time.time()), 1)

            for i, c2 in enumerate(block2_cands):
                c = candidates[i]
                if(c.decode_completed and not c.msg):
                    if (self.spectrum.audio_in.main_ptr > c2.last_payload_hop and not c2.demap_started):
                        c2.demap(self.spectrum)
                        if(c2.llr_sd > c.llr_sd and not c2.decode_completed):
                            c2.decode()
                            if(c2.msg):
                                candidates.append(c2)
                                candidates.remove(c)
                
            for c in candidates:
                if (self.spectrum.audio_in.main_ptr > c.last_payload_hop and not c.demap_started):
                    c.demap(self.spectrum)
                    
            to_decode = [c for c in candidates if c.llr_sd > 0 and not c.decode_completed]
            to_decode.sort(key = lambda c: -c.llr_sd) # in case of emergency (timeouts) process best first
            for c in to_decode[:25]:
                c.decode()

            for c in candidates:
                if(c.msg):
                    c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                    if(not c.dedupe_key in duplicate_filter):
                        duplicate_filter.add(c.dedupe_key)
                        if(self.on_decode):
                            self.on_decode(c.decode_dict)
                    
    def check_for_tx(self):
        tx_msg_file = 'PyFT8_tx_msg.txt'
        if os.path.exists(tx_msg_file):
            if(not self.output_device_idx):
                global_time_utils.tlog("[Tx] Tx message file found but no output device specified", verbose = True)
                return
            with open(tx_msg_file, 'r') as f:
                tx_msg = f.readline().strip()
                tx_freq = f.readline().strip()
            tx_freq = int(tx_freq) if tx_freq else 1000    
            global_time_utils.tlog(f"[TX] transmitting {tx_msg} on {tx_freq} Hz", verbose = self.verbose)
            os.remove(tx_msg_file)
            symbols = self.audio_out.create_ft8_symbols(tx_msg_file)
            audio_data = self.audio_out.create_ft8_wave(symbols, f_base = tx_freq)
            self.audio_out.play_data_to_soundcard(audio_data, self.output_device_idx)
            global_time_utils.tlog("[Tx] done transmitting", verbose = self.verbose)
                         
