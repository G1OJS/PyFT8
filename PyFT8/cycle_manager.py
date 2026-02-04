import threading
import numpy as np
import time
from PyFT8.FT8_unpack import FT8_unpack
from PyFT8.FT8_crc import check_crc_codeword_list
from PyFT8.candidate import Candidate
from PyFT8.spectrum import Spectrum
from PyFT8.ldpc import LdpcDecoder
from PyFT8.osd import osd_decode_minimal
from PyFT8.audio import find_device
from PyFT8.time_utils import tlog, cycle_time, cyclestart_str

import os

class Cycle_manager():
    def __init__(self, sigspec, on_decode, on_occupancy = None, on_decode_include_failures = False,
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200, 3100], verbose = False):
        
        self.spectrum = Spectrum(sigspec, 12000, freq_range[1], 4, 2)
        self.running = True
        self.verbose = verbose
        self.freq_range = freq_range
        self.f0_idxs = range(int(freq_range[0]/self.spectrum.df),
                        min(self.spectrum.nFreqs - self.spectrum.fbins_per_signal, int(freq_range[1]/self.spectrum.df)))
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.cands_list = []
        self.new_cands = []
        self.on_decode = on_decode
        self.on_decode_include_failures = on_decode_include_failures
        self.on_occupancy = on_occupancy
        self.duplicate_filter = set()
        if(self.output_device_idx):
            from .audio import AudioOut
            self.audio_out = AudioOut
        self.audio_started = False
        self.cycle_seconds = sigspec.cycle_seconds
        threading.Thread(target=self.manage_cycle, daemon=True).start()

    def analyse_hoptimes(self):
        if not any(self.spectrum.audio_in.hoptimes): return
        diffs = np.ediff1d(self.spectrum.audio_in.hoptimes)
        if(self.verbose):
            m = 1000*np.mean(diffs)
            s = 1000*np.std(diffs)
            pc = int(100*s /(1000/self.spectrum.sigspec.symbols_persec) )
            tlog(f"[Cycle manager] Hop timings: mean = {m:.2f}ms, sd = {s:.2f}ms ({pc:5.1f}% symbol)")

    def pack_and_send_decode(self, c):
        td = f"{c.decode_completed %60:4.1f}" if c.decode_completed else '     '
        decode_dict = {'cs':c.cyclestart_str, 'f':c.fHz, 'msg':' '.join(c.msg), 'snr':c.snr,
             'dt':c.dt, 'td':td, 'ncheck0':c.ncheck0, 'llr0_sd':c.llr0_sd, 'decode_path':c.decode_path}
        self.on_decode(decode_dict)

    def manage_cycle(self):
        cycle_searched = True
        cycle_time_prev = 0
        to_demap = []
        with_message = []
        delay = self.spectrum.sigspec.cycle_seconds - cycle_time()
        tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)\n")

        while self.running:
            time.sleep(0.001)
            rollover = cycle_time() < cycle_time_prev 
            cycle_time_prev = cycle_time()

            if(rollover):
                if(self.verbose):
                    tlog(f"[Cycle manager] rollover detected at {cycle_time():.2f}")
                cycle_searched = False
                cands_rollover_done = False
                self.check_for_tx()
                self.spectrum.audio_in.grid_main_ptr = 0
                self.analyse_hoptimes()
                self.spectrum.audio_in.hoptimes = []
                if not self.audio_started:
                    self.audio_started = True
                    self.spectrum.audio_in.start_live(self.input_device_idx, self.spectrum.dt)

            if (self.spectrum.audio_in.grid_main_ptr > self.spectrum.h_search and not cycle_searched):
                cycle_searched = True
                if(self.verbose):
                    tlog(f"[Cycle manager] Search spectrum ...")
                self.new_cands = self.spectrum.search(self.f0_idxs, cyclestart_str(time.time()))
                if(self.on_decode_include_failures):
                    completed = [c for c in self.cands_list if c.decode_completed and not c.msg]
                    for c in completed:
                        self.pack_and_send_decode(c)
                if(self.verbose):
                    tlog(f"[Cycle manager] Spectrum searched -> {len(self.new_cands)} candidates")
                    n_unprocessed = len([c for c in self.cands_list if not "#" in c.decode_path])
                    tlog(f"[Cycle manager] {n_unprocessed} unprocessed candidates detected")
                    nf, ns = len(completed), len(with_message)
                    tlog(f"[Cycle manager] last cycle had {nf} failed candidates and {ns} decodes (total = {nf+ns})")                    
                    
                self.cands_list = self.new_cands
                if(self.on_occupancy):
                    self.on_occupancy(self.spectrum.occupancy, self.spectrum.df)

            for c in self.cands_list:
                if (self.spectrum.audio_in.grid_main_ptr > c.last_payload_hop and not c.demap_started):
                    c.demap(self.spectrum)

            to_decode = [c for c in self.cands_list if c.demap_completed and not c.decode_completed]
            to_decode.sort(key = lambda c: -c.llr0_sd) # in case of emergency (timeouts) process best first
            for c in to_decode[:25]:
                c.decode()

            with_message = [c for c in self.cands_list if c.msg]
            for c in with_message:
                c.dedupe_key = c.cyclestart_str+" "+' '.join(c.msg)
                if(not c.dedupe_key in self.duplicate_filter):
                    self.duplicate_filter.add(c.dedupe_key)
                    c.call_a, c.call_b, c.grid_rpt = c.msg[0], c.msg[1], c.msg[2]
                    self.pack_and_send_decode(c)
                    
    def check_for_tx(self):
        tx_msg_file = 'PyFT8_tx_msg.txt'
        if os.path.exists(tx_msg_file):
            if(not self.output_device_idx):
                tlog("[Tx] Tx message file found but no output device specified")
                return
            with open(tx_msg_file, 'r') as f:
                tx_msg = f.readline().strip()
                tx_freq = f.readline().strip()
            tx_freq = int(tx_freq) if tx_freq else 1000    
            tlog(f"[TX] transmitting {tx_msg} on {tx_freq} Hz")
            os.remove(tx_msg_file)
            symbols = self.audio_out.create_ft8_symbols(tx_msg_file)
            audio_data = self.audio_out.create_ft8_wave(symbols, f_base = tx_freq)
            self.audio_out.play_data_to_soundcard(audio_data, self.output_device_idx)
            tlog("[Tx] done transmitting")
                         
