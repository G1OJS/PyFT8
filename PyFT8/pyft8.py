import argparse
import time
import os
import threading
import pickle
import numpy as np
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.gui import Gui
from PyFT8.transmitter import AudioOut
from PyFT8.time_utils import global_time_utils

MAX_TX_START_SECONDS = 2.5
T_CYC = 15
global rig
rig = None

def load_rigctrl():
    try:
        from PyFT8.rigctrl import Rig
        print("Loaded Rig control")
        return Rig()
    except ImportError:
        print("No Rig control found")
        return None
 
def get_config(config_folder):
    import configparser
    global config
    config = configparser.ConfigParser()
    ini_file = f"{config_folder}/PyFT8.ini"
    if not os.path.exists(ini_file):
        config['station'] = {'call':'station_callsign', 'grid':'station_grid'}
        config['bands'] = {'20m':14.074}
        with open(ini_file, 'w') as f:
            config.write(f)
        print(f"Wrote default config to {ini_file}")
    print(f"Reading config from {ini_file}")
    config.read(ini_file)

class Logging:
    def __init__(self, config_folder):
        self.adif_log_file = f"{config_folder}/PyFT8.adi"
        self.worked_before_file = f"{config_folder}/PyFT8_wb.pkl"
        self.check_files()

    def check_files(self):
        if(not os.path.exists(self.adif_log_file)):
            with open(self.adif_log_file, 'w') as f:
                f.write("header <eoh>")
        if(not os.path.exists(self.worked_before_file)):
            with open(f"{self.worked_before_file}","wb") as f:
                pickle.dump({'dummy':'dummy'}, f)

    def update_worked_before(self, callsign, time_on):
        with open(f"{self.worked_before_file}","rb") as f:
            worked_before = pickle.load(f)
        if not callsign in worked_before:
            worked_before[callsign] = {}
        worked_before[callsign] = {time_on}
        with open(f"{self.worked_before_file}","wb") as f:
            pickle.dump(worked_before, f)
                
    def log(self, times, band_info, mStation, oStation, rpts):
        log_dict = {'call':oStation['c'], 'gridsquare':oStation['g'], 'mode':'FT8',
        'operator':mStation['c'], 'station_callsign':mStation['c'], 'my_gridsquare':mStation['g'], 
        'rst_sent':rpts['sent'], 'rst_rcvd':rpts['rcvd'], 
        'qso_date':time.strftime("%Y%m%d", times['time_on']), 'qso_date_off':time.strftime("%Y%m%d", times['time_off']),
        'time_on':time.strftime("%H%M%S", times['time_on']), 'time_off':time.strftime("%H%M%S", times['time_on']),
        'band':band_info['b'], 'freq':band_info['f']}
        with open(self.adif_log_file,'a') as f:
            f.write(f"\n")
            for k, v in log_dict.items():
                v = str(v)
                f.write(f"<{k}:{len(v)}>{v} ")
            f.write(f"<eor>\n")
        self.update_worked_before(oStation['c'], times['time_on'])


class FT8_QSO:
    def __init__(self, logging):
        self.logging = logging
        self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.band_info = {'b':None, 'f':0}
        threading.Thread(target = self._transmitter, daemon = True).start()
        self.clear()

    def clear(self):
        self.message_to_transmit = None
        self.last_tx = None
        self.tx_cycle = None
        self.oStation = {'c':None, 'g':None}
        self.times = {'time_on':None, 'time_off':None}
        self.rpts = {'sent': None, 'rcvd': None}
        
    def set_tx_message(self, message):
        if self.band_info['b'] is None:
            gui.simple_message("Please select a band before transmitting", color = 'red')
            return
        print(f"Set transmit message to '{message}' with tx cycle = {self.tx_cycle}")
        self.message_to_transmit = message

    def _transmitter(self):
        while True:
            time.sleep(0.1)
            if self.message_to_transmit is None:
                continue
            if output_device_idx is None:
                print("No output device")
                return
            ct = global_time_utils.cycle_time()
            if ct > MAX_TX_START_SECONDS:
                delay = 15.25 - ct
                time.sleep(delay)
            if self.tx_cycle is None:
                self.tx_cycle = global_time_utils.curr_cycle_from_time()
            print(f"Transmitting {self.message_to_transmit} on cycle {self.tx_cycle}")
            symbols = audio_out.create_ft8_symbols(self.message_to_transmit)
            audio_data = audio_out.create_ft8_wave(symbols, f_base = clear_frequencies[self.tx_cycle])
            rig.PyFT8_ptt_on()
            audio_out.play_data_to_soundcard(audio_data, output_device_idx)
            rig.PyFT8_ptt_off()
            self.last_tx = self.message_to_transmit
            self.message_to_transmit = None

    def log(self):
        self.logging.log(self.times, self.band_info, self.mStation, self.oStation, self.rpts)

def isReport(grid_rpt):     return "+" in grid_rpt or "-" in grid_rpt
def isRReport(grid_rpt):    return isReport(grid_rpt) and 'R' in grid_rpt
def isRRR(grid_rpt):        return 'RRR' in grid_rpt
def isRR73(grid_rpt):       return 'RR73' in grid_rpt
def is73(grid_rpt):         return '73' in grid_rpt and not isRR73(grid_rpt)
def isGrid(grid_rpt):       return not isReport(grid_rpt) and not is73(grid_rpt) and not isRR73(grid_rpt) and not isRRR(grid_rpt) 

def progress_qso(clicked_msg, their_snr, their_cycle_start_time):
    global qso
    if time.time() - their_cycle_start_time > (15 + MAX_TX_START_SECONDS):
        print("Try next cycle")
        return
    
    call_a, call_b, grid_rpt, _ = clicked_msg.split()
    my_station = qso.mStation
    reply = ""

    if call_a == "CQ":
        qso.clear()
        qso.times['time_on'] = time.gmtime()
        qso.oStation = {'c': call_b, 'g': grid_rpt}
        qso.set_tx_message(f"{qso.oStation['c']} {my_station['c']} {my_station['g']}")
        return

    if call_a == my_station['c']:
        if qso.times['time_on'] is None:
            qso.times['time_on'] = time.gmtime()
        qso.oStation['c'] = call_b
        if isGrid(grid_rpt):
            qso.oStation = {'c': call_b, 'g': grid_rpt}
            qso.rpts['sent'] = f"{their_snr:+03d}"
            reply = f"{qso.oStation['c']} {my_station['c']} {their_snr:+03d}"
        if isReport(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} R{their_snr:+03d}"
            qso.rpts['rcvd'] = grid_rpt[-3:]
        if isRReport(grid_rpt) or isRRR(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} RR73"
        if isRR73(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} 73"
        qso.set_tx_message(reply)
        
    if is73(grid_rpt) or " 73" in reply or isRR73(grid_rpt):
        qso.times['time_off'] = time.gmtime()
        qso.log()
        qso.clear()

def make_wav(msg, wave_output_file): # move to transmitter.py?
    symbols = audio_out.create_ft8_symbols(msg)
    audio_data = audio_out.create_ft8_wave(symbols)
    audio_out.write_to_wave_file(audio_data, wave_output_file)
    print(f"Created wave file {wave_output_file}")

def wait_for_keyboard():
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

#============= Callbacks for GUI ==========================================================
def on_decode(c):
    if gui:
        message_cycle_started = global_time_utils.cyclestart_time(time.time())
        txt = f"{c.msg} ({c.snr:+03d})"
        gui.post_decode((c.h0_idx, c.f0_idx, txt, (c.snr, message_cycle_started)))
    print(f"{c.cyclestart_str} {c.snr} {c.dt:4.1f} {c.fHz} ~ {c.msg}")

def on_busy_profile(busy_profile, cycle):
    if output_device_idx is None:
        return
    fmax = 950 if qso.band_info['b']=='60m' else 2000
    f0_idx, fn_idx = int(500/audio_in.df), int(fmax/audio_in.df)
    idx = np.argmin(busy_profile[f0_idx:fn_idx])
    clear_frequencies[cycle] = (f0_idx + idx) * audio_in.df
    print(f"Set Tx freq to {clear_frequencies[cycle]:6.1f} for cycle {cycle}")

def on_control_click(btn_widg):
    btn_text, btn_data = btn_widg.label.get_text(), btn_widg.data
    if btn_text == "CQ":
        mc, mg = config['station']['call'], config['station']['grid']
        qso.set_tx_message(f"CQ {mc} {mg}")
    if btn_text == "Repeat last":
        qso.set_tx_message(qso.last_tx)
    if btn_text == "Tx off":
        rig.PyFT8_ptt_off()
        qso.clear()
    if('m' in btn_text):
        qso.band_info = {'b':btn_text, 'f':btn_data}
        rig.PyFT8_set_freq_Hz(int(1000000*float(qso.band_info['f'])))
        gui.simple_message(f"{qso.band_info['b']} {qso.band_info['f']}", 'black')

def on_msg_click(clicked_msg, their_snr, their_cycle_start_time):
    progress_qso(clicked_msg, their_snr, their_cycle_start_time)

#=============== CLI ========================================================================        
def cli():
    global audio_in, audio_out, output_device_idx, rig, gui, qso, config, clear_frequencies
    import time
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-c', '--config_folder', help = 'Location of config folder e.g. C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg', default = './') 
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')    
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device')
    parser.add_argument('-n','--no_gui',  action='store_true',  help = "Don't create a gui")
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file name', default = 'PyFT8.wav')
    args = parser.parse_args()

    output_device_idx = None
    config_folder = f"{args.config_folder}".strip()
    get_config(config_folder)
    logging = Logging(config_folder)
    qso = FT8_QSO(logging)
    rig = load_rigctrl()

 #   qso.band_info = {'b':'20m','f':14.074}
 #   qso.oStation = {'c':'T1EST', 'g':'TT11'}
 #   qso.times = {'time_on':time.gmtime(), 'time_off':time.gmtime()}
 #   qso.rpts = {'sent':-1, 'rcvd':-1}
 #   qso.log()

    if args.transmit_message or args.outputcard_keywords:
        audio_out = AudioOut()
        clear_frequencies = [760, 760]
    
    if args.outputcard_keywords:
        outputcard_keywords = args.outputcard_keywords.replace(' ','').split(',')
        output_device_idx = audio_out.find_device(outputcard_keywords)
            
    if args.transmit_message:
        if args.outputcard_keywords:
            qso.set_tx_message(args.transmit_message)
        else:
            make_wav(args.transmit_message, f"{args.config_folder}/{args.wave_output_file}")      
    else:
        audio_in = AudioIn(3100)
        input_device_idx = audio_in.find_device(args.inputcard_keywords.replace(' ','').split(','))
        if not input_device_idx:
            print("No input device")
        else:
            gui = None if args.no_gui else Gui(audio_in.dBgrid_main, 4, 2, config, on_msg_click, on_control_click)
            rx = Receiver(audio_in, [200, 3100], on_decode, on_busy_profile)
            audio_in.start_streamed_audio(input_device_idx)
            if gui is not None:
                gui.plt.show()
            else:
                wait_for_keyboard()


#================== TEST CODE ============================================================
print(__name__)
if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-n']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-cC:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-o', "Speak, CODEC"]):
        cli()
