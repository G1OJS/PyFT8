import argparse
import time
import os
import threading
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
        
def get_config():
    import configparser
    global config
    config = configparser.ConfigParser()
    if not os.path.exists(ini_file):
        config['station'] = {'call':'station_callsign', 'grid':'station_grid'}
        config['bands'] = {'20m':14.074}
        with open(ini_file, 'w') as f:
            config.write(f)
        print(f"Wrote default config to {ini_file}")
    print(f"Reading config from {ini_file}")
    config.read(ini_file)

class FT8_QSO:
    def __init__(self):
        self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.band_info = {'b':None, 'f':0}
        self.start()

    def start(self):
        self.last_tx = {'msg':None,'cycle':None}
        self.oStation = {'c':None, 'g':None}
        self.times = {'time_on':None, 'time_off':None}
        self.rpts = {'sent': None, 'rcvd': None}
        
    def log_to_adif(self):
        log_dict = {'call':self.oStation['c'], 'gridsquare':self.oStation['g'], 'mode':'FT8',
        'operator':self.mStation['c'], 'station_callsign':self.mStation['c'], 'my_gridsquare':self.mStation['g'], 
        'rst_sent':self.rpts['sent'], 'rst_rcvd':self.rpts['rcvd'], 
        'qso_date':time.strftime("%Y%m%d", self.times['time_on']), 'qso_date_off':time.strftime("%Y%m%d", self.times['time_off']),
        'time_on':time.strftime("%H%M%S", self.times['time_on']), 'time_off':time.strftime("%H%M%S", self.times['time_on']),
        'band':self.band_info['b'], 'freq':self.band_info['f']}
        if(not os.path.exists(adif_log_file)):
            with open(adif_log_file, 'w') as f:
                f.write("header <eoh>")
        with open(adif_log_file,'a') as f:
            f.write(f"\n")
            for k, v in log_dict.items():
                v = str(v)
                f.write(f"<{k}:{len(v)}>{v} ")
            f.write(f"<eor>\n")

def isReport(grid_rpt):     return "+" in grid_rpt or "-" in grid_rpt
def isRReport(grid_rpt):    return isReport(grid_rpt) and 'R' in grid_rpt
def isRRR(grid_rpt):        return 'RRR' in grid_rpt
def isRR73(grid_rpt):       return 'RR73' in grid_rpt
def is73(grid_rpt):         return '73' in grid_rpt and not isRR73(grid_rpt)
def isGrid(grid_rpt):       return not isReport(grid_rpt) and not is73(grid_rpt) and not isRR73(grid_rpt) and not isRRR(grid_rpt) 

def progress_qso(clicked_msg, msg_params):
    global qso
    their_snr, their_cycle_start_time = msg_params
    if time.time() - their_cycle_start_time > (15 + MAX_TX_START_SECONDS):
        print("Try next cycle")
        return
    
    call_a, call_b, grid_rpt, _ = clicked_msg.split()
    my_station = qso.mStation
    reply = ""

    if call_a == "CQ":
        qso.start()
        qso.times['time_on'] = time.gmtime()
        qso.oStation = {'c': call_b, 'g': grid_rpt}
        reply = f"{qso.oStation['c']} {my_station['c']} {my_station['g']}"
        transmit_threaded(reply)
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
        transmit_threaded(reply)
        
    if is73(grid_rpt) or " 73" in reply or isRR73(grid_rpt):
        qso.times['time_off'] = time.gmtime()
        qso.log_to_adif()

def make_wav(msg, wave_output_file): # move to transmitter.py?
    symbols = audio_out.create_ft8_symbols(msg)
    audio_data = audio_out.create_ft8_wave(symbols)
    audio_out.write_to_wave_file(audio_data, wave_output_file)
    print(f"Created wave file {wave_output_file}")    

def transmit_threaded(msg): # move to transmitter.py?
    threading.Thread(target = transmit, args = (msg,), daemon = True).start()

def transmit(msg): # move to transmitter.py?
    if output_device_idx is None:
        print("No output device")
        return
    if msg is None:
        return
    if qso.band_info['b'] is None:
        gui.simple_message("Please select a band", 'red')
        return
    print(f"Transmit {msg}")
    symbols = audio_out.create_ft8_symbols(msg)
    curr_cycle, curr_cycle_time = global_time_utils.curr_cycle_from_time()
    tx_cycle = curr_cycle if curr_cycle_time < MAX_TX_START_SECONDS else 1-curr_cycle
    audio_data = audio_out.create_ft8_wave(symbols, f_base = clear_frequencies[tx_cycle])
    ct = global_time_utils.cycle_time()
    if ct > MAX_TX_START_SECONDS:
        delay = 15.25 - ct
        time.sleep(delay)
    qso.last_tx = {'msg':msg}
    print(f"Transmitting {qso.last_tx['msg']}")
    rig.PyFT8_ptt_on()
    audio_out.play_data_to_soundcard(audio_data, output_device_idx)
    rig.PyFT8_ptt_off()
    return True

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
    print(btn_text, btn_data)
    if btn_text == "CQ":
        mc, mg = config['station']['call'], config['station']['grid']
        transmit_threaded(f"CQ {mc} {mg}")
    if btn_text == "Repeat last":
        transmit_threaded(qso.last_tx['msg'])
    if btn_text == "Tx off":
        rig.PyFT8_ptt_off()
    if('m' in btn_text):
        qso.band_info = {'b':btn_text, 'f':btn_data}
        rig.PyFT8_set_freq_Hz(int(1000000*float(qso.band_info['f'])))
        gui.simple_message(f"{qso.band_info['b']} {qso.band_info['f']}", 'black')

def on_msg_click(clicked_msg, msg_params):
    progress_qso(clicked_msg, msg_params)

#=============== CLI ========================================================================        
def cli():
    global audio_in, audio_out, output_device_idx, rig, gui, qso, ini_file, adif_log_file, clear_frequencies
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
    ini_file = f"{args.config_folder}/PyFT8.ini".strip()
    get_config()
    qso = FT8_QSO()
    rig = load_rigctrl()

    if args.transmit_message or args.outputcard_keywords:
        audio_out = AudioOut()
        clear_frequencies = [760, 760]
    
    if args.outputcard_keywords:
        outputcard_keywords = args.outputcard_keywords.replace(' ','').split(',')
        output_device_idx = audio_out.find_device(outputcard_keywords)
        adif_log_file = f"{args.config_folder}/PyFT8.adi"
            
    if args.transmit_message:
        if not transmit(args.transmit_message):
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
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC', '-cC:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-n']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-cC:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-o', "Speak, CODEC"]):
        cli()
