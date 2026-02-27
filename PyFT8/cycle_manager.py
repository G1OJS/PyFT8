import threading
import numpy as np
import time
from PyFT8.candidate import Candidate
from PyFT8.spectrum import Spectrum
from PyFT8.audio import find_device
from PyFT8.time_utils import global_time_utils
import os

class Cycle_manager():
    def __init__(self, sigspec, on_decode, wav_input = None, run = True, on_finished = False, 
                 input_device_keywords = None, output_device_keywords = None,
                 freq_range = [200, 3100], verbose = False):
        self.spectrum = Spectrum(sigspec, 12000, freq_range[1], 4, 2)
        self.verbose = verbose
        self.f0_idxs = range(int(freq_range[0]/self.spectrum.df),
                        min(self.spectrum.nFreqs - self.spectrum.fbins_per_signal, int(freq_range[1]/self.spectrum.df)))
        self.input_device_idx = find_device(input_device_keywords)
        self.output_device_idx = find_device(output_device_keywords)
        self.on_decode = on_decode
        self.on_finished = on_finished
        self.wav_input = wav_input
        if(self.output_device_idx):
            from PyFT8.audio import AudioOut
            self.audio_out = AudioOut
        if(self.wav_input is None):
            self.spectrum.audio_in.start_live(self.input_device_idx)
            delay = self.spectrum.sigspec.cycle_seconds - global_time_utils.cycle_time()
            global_time_utils.tlog(f"[Cycle manager] Waiting for cycle rollover ({delay:3.1f}s)\n")
            time.sleep(delay)
        else:
            global_time_utils.set_global_offset(0)
            global_time_utils.set_global_offset(global_time_utils.cycle_time() + 1)
            threading.Thread(target=self.spectrum.audio_in.load_wav, args = (self.wav_input, self.spectrum.dt, ),  daemon=True).start()

        if(run):
            threading.Thread(target=self.manage_cycle, daemon=True).start()

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
        
    def manage_cycle(self):
        dashes = "======================================================"
        candidates = []
        duplicate_filter = set()
        rollover = global_time_utils.new_ticker(0)
        search = global_time_utils.new_ticker(11)

        def summarise_cycle():
            unfinished = [c for c in candidates if not c.decode_completed]
            nu = len(unfinished)
            if(self.on_finished):
                self.on_finished({"n_unfinished":nu, "spec_df":self.spectrum.df})
            if(self.verbose):
                with_message = [c for c in candidates if c.msg]
                failed = [c for c in candidates if c.decode_completed and not c.msg]
                ns, nf = len(with_message), len(failed)
                global_time_utils.tlog(f"[Cycle manager] Last cycle had {ns} decodes, {nf} failures and {nu} unfinished (total = {ns+nf+nu})")   

        self.spectrum.audio_in.main_ptr = 0
        main_ptr_prev = 0
        while not self.spectrum.audio_in.wav_finished:
            time.sleep(0.001)
            ptr = self.spectrum.audio_in.main_ptr
            if(ptr != main_ptr_prev):
                main_ptr_prev = ptr

                new_to_decode = []
                for c in candidates:
                    if ptr > c.last_payload_hop and not c.demap_started:
                        c.demap(self.spectrum)
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
                    self.check_for_tx()
                    self.spectrum.audio_in.main_ptr = 0
                if (global_time_utils.check_ticker(search)):
                    summarise_cycle()
                    global_time_utils.tlog(f"[Cycle manager] start search at hop { self.spectrum.audio_in.main_ptr}", verbose = self.verbose)
                    candidates = self.spectrum.search(self.f0_idxs, global_time_utils.cyclestart_str(time.time()))
                    global_time_utils.tlog(f"[Cycle manager] New spectrum searched -> {len(candidates)} candidates", verbose = self.verbose) 

        summarise_cycle() # for wav files that have just finished

                         
