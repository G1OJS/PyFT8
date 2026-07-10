import argparse
import time, sys
import os
import threading
import pickle
import numpy as np
from PyFT8.receiver import Receiver
from PyFT8.pskreporter import PSKR_upload
from PyFT8.gui import Gui
from PyFT8.transmitter import AudioOut
from PyFT8.time_utils import time_utils
from PyFT8.rigctrl import Rig_hamlib, Rig_CAT
from PyFT8.databases import History, ADIF
from PyFT8.qso_manager import QSO_manager

VER = '3.2.0 test'
PSKR_REFRESH_MINS = 20

gui = None
history = None
myCall, myGrid = None, None

def get_config(config_folder):
    import configparser, sys
    config = configparser.ConfigParser()
    ini_file = f"{config_folder}/PyFT8.ini"
    if not os.path.exists(ini_file):
        resp = input(f"No config file found at {ini_file}\nWould you like to create one (Y/N)? ")
        if resp.upper() !="Y":
            print("Exiting program")
            sys.exit()
        station_callsign = input(f"Please enter your callsign: ")
        station_grid = ''
        while len(station_grid) < 4:
            station_grid = input(f"Please enter your Maidenhead locator (at least 4 characters, you can edit this later): ")
        config['station'] = {'call':station_callsign, 'grid':station_grid}
        config['bands'] = {'20m':14.074}
        config['gui'] = {'loc':'km_deg', 'wb':'Y'}
        config['hamlib_rig'] = {'rigctld':'C:/WSJT/wsjtx/bin/rigctld-wsjtx', 'port': 'COM4', 'baud_rate':9600, 'model':3070}
        config['pskreporter'] = {'upload':'Y'}
        with open(ini_file, 'w') as f:
            config.write(f)
        print(f"Wrote default config to {ini_file}. Please open and edit to add bands, frequencies and preferences and re-launch the program.")
        sys.exit()
    print(f"Reading config from {ini_file}")
    config.read(ini_file)
    return config

def console_print(text, color = 'white'):
    text = f"{time_utils.cycle_time():4.1f} {text}"
    if gui is not None:
        gui.console.scroll_print(text, color)
    else:
        print(text)

def wait_for_keyboard():
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


class Transmitter():
    def __init__(self):
        self.tx_message = None

    def start_daemon(self):
        threading.Thread(target = self.td, daemon = True).start()

    def td(self):
        while True:
            time.sleep(0.1)
            if self.tx_message is not None:
                start_gridtime = self.tx_message['start_gridtime'] 
                grid_time = time_utils.grid_time()
                if start_gridtime <= grid_time < start_gridtime + MAX_TX_START_CYCLETIME:
                    transmit(self.tx_message['text'])
                    self.tx_message = None

    def transmit(self, text):
        symbols = audio_out.create_ft8_symbols(self.message_to_transmit)
        if any(symbols):
            console_print(f"[PyFT8] Transmitting {self.tx_message}")
            audio_data = audio_out.create_ft8_wave(symbols, f_base = self.tx_freq)
            rig.ptt_on()
            audio_out.play_data_to_soundcard(audio_data, output_device_idx)
            rig.ptt_off()
            self.last_tx = self.message_to_transmit
            self.message_to_transmit = None
        else:
            console_print(f"[PyFT8] Couldn't encode message {self.message_to_transmit}", color = 'red') # move this to earlier by setting tx symbols not tx message


def on_decode(c):
    band_info = gui.qso.band_info if gui else {'current_band': None, 'fMHz':0, 'time_set':0}
    if gui:
        #if (c.decode_completed - band_info['time_set']) < 9: # prevent bad QRG -> heard_by_me and pskreporter upload data
        #    return
        geo_text = history.get_geo_text(c.msg_tuple[1], myGrid) if history else ''
        tnow = time_utils.time()
        wb_time = adif_logging.cache.get(c.msg_tuple[1],'') if adif_logging else 0
        wb_text = f"wb: {time_utils.format_duration(tnow - float(wb_time))}" if wb_time else ''
        hearing_me = ''
        if history:
            hearing_me = '# ' if history.is_hearing_me(band, c.msg_tuple[1], tnow - 60*HEARING_PANEL_LIFE_MINS) else ' '
        gui.add_message_box({'origin':c.origin,
                            'msg_tuple':c.msg_tuple,
                            'is_from_me': msg_tuple[1] == myCall,
                            'is_to_me': msg_tuple[0] == myCall,
                            'is_cq': msg_tuple[0].startswith('CQ'),
                            'display_text': f"{' '.join(c.msg_tuple)} {hearing_me}{wb_text} {self.geo_text}"})

    screen_format = f"{c.cyclestart['string']} {c.snr:+03d} {c.dt:4.1f} {c.fHz:4.0f} ~ {' '.join(c.msg_tuple)}"
    print(f"{time_utils.cycle_time():5.1f} {screen_format}")
    
    if history:
        history.write_all_txt_row(c.cyclestart['string'], band_info['fMHz'], 'Rx', 'FT8', c.snr, c.dt, c.fHz, ' '.join(c.msg_tuple))
        
    if band_info['current_band'] is not None and pskr_upload is not None:
        call_a, call_b, grid_rpt = c.msg_tuple
        if call_b == 'not':
            return
        call_b_grid = grid_rpt if isGrid(grid_rpt) else ''
        if call_b != self.myCall:
            pskr_upload.add_report(call_b, int(1000000*float(band_info['fMHz'])) + c.fHz, c.snr, 'FT8', 1, int(time_utils.time()))
            if history:
                history.store_best_grid(call_b, call_b_grid)
                history.add_myspots_record(history.heard_by_me.data, history.heard_by_me_new, band_info['current_band'], call_b, int(time_utils.time()), c.snr)
        if history and call_b == self.myCall and (isReport(grid_rpt) or isRReport(grid_rpt)):
            rpt = grid_rpt.replace("R","")
            history.add_myspots_record(history.hearing_me.data, history.hearing_me_new, band_info['current_band'], call_a, int(time_utils.time()), rpt)

def find_clear_freq(busy_profile_new, df, cycle):
    global busy_profile, clearest_frequency
    if output_device_idx is None:
        return
    if busy_profile is not None:
        busy_profile += busy_profile_new
        fmax = 950 if qso.band_info['b']=='60m' else 2000
        f0_idx, fn_idx = int(500/df), int(fmax/df)
        idx = np.argmin(busy_profile[f0_idx:fn_idx])
        clearest_frequency = (f0_idx + idx) * df
    busy_profile = busy_profile_new
    #self.gui.console.scroll_print(f"[on_busy] Clear Tx frequency found at {clearest_frequency:6.1f}")

def cli():
    global myCall, myGrid, history
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-c', '--config_folder', help = 'Location of config folder e.g. C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg', default = './') 
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device')  
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device')
    parser.add_argument('-n','--no_gui',  action='store_true',  help = "Don't create a gui")
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file name')
    parser.add_argument('-a', '--parse_all_file', action='store_true', help = 'parse and save .../config_folder/ALL.txt to heard me / heard by me data') 
    args = parser.parse_args()

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.transmit_message or args.outputcard_keywords:
        audio_out = AudioOut()
        clearest_frequency = 760

    if args.transmit_message and args.wave_output_file:
        audio_out.make_wav(args.transmit_message, f"{args.wave_output_file}")
        console_print(f"Created wave file {wave_output_file}")
        sys.exit(1)
    
    config_folder = f"{args.config_folder}".strip()
    config = get_config(config_folder)
    myCall, myGrid = config['station']['call'], config['station']['grid']

    if args.parse_all_file:
        history = History(config_folder, mc, mg, PSKR_REFRESH_MINS)
        history.load_hearing_heard_from_all_file(config['bands'])
        history.hearing_me.save()
        history.heard_by_me.save()
        print("All file parsed and saved to hearing_me / heard_by_me files")
        sys.exit(1)

    if config.has_section('hamlib_rig'):
        console_print("Connecting to rig via Hamlib")
        rig = Rig_hamlib(config)
    else:
        console_print("Connecting to rig via CAT")
        rig = Rig_CAT(config)

    if config.has_section('launch'):
        os.system(config['launch']['app'])

    if args.outputcard_keywords:
        outputcard_keywords = args.outputcard_keywords.replace(' ','').split(',')
        output_device_idx = audio_out.find_device(outputcard_keywords)

        if args.transmit_message and rig and args.outputcard_keywords:
            transmitter = Transmitter()
            transmitter.transmit(args.transmit_message)
            sys.exit(1)
        
    if not args.inputcard_keywords:
        print("No input device specified")
        sys.exit(1)
    else:
        input_device_keywords = args.inputcard_keywords.replace(' ','').split(',')
        rx = Receiver([100, 3000], input_device_keywords, wav_files = None, on_decode = on_decode,
                      sync_score_min = 100, max_cands = 75, osd = False, ldpc = [45,15], min_search_start = 11)

    if not args.no_gui:
        gui = Gui(config)
        gui.init_waterfall(rx.audio_in.waterfall_data)
        transmitter = Transmitter()
        transmitter.start_daemon()
        station = config['station']
        gui.qso_manager = QSO_manager(station['call'], station['grid'], gui, transmitter)
        history = History(config_folder, myCall, myGrid, PSKR_REFRESH_MINS)
        adif_logging = ADIF(f"{config_folder}/PyFT8.adi")
        history.load_hearing_heard_from_adif(adif_logging.cache)
        history.start_collect_new()
        
    if myCall is not None and 'pskreporter' in config.keys():
        if config['pskreporter']['upload'] == 'Y':
            pskr_upload = PSKR_upload(myCall, myGrid, software = f"PyFT8 v{VER}", console_print = console_print) if not myCall is None else None

    if gui is None:
        wait_for_keyboard()
    else:
        gui.set_bandstats_title(f"Pskreporter Spots\nto/from {config['station']['grid'][:4]} <{PSKR_REFRESH_MINS:.0f} mins")
        gui.plt.show()


#================== TEST CODE ============================================================
if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg', '-a']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-n', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", "-w", "PyFT8.wav"]):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-o', "Speak, CODEC", '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
        cli()
