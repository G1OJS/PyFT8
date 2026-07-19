import argparse, sys, os
import configparser
from PyFT8.time_utils import time_utils
from PyFT8.receiver import Receiver
from PyFT8.pskreporter import PSKR_upload
from PyFT8.gui import Gui
from PyFT8.transmitter import get_ft8_symbols, symbols_to_audio_bytes, write_wav_file, SoundcardOut
from PyFT8.rigctrl import Rig_hamlib, Rig_CAT
from PyFT8.databases import History
from PyFT8.databases import ADIF
from PyFT8.qso_manager import QSO_manager
from PyFT8.message_broker import Broker

VER = '3.6.5'
PSKR_REFRESH_MINS = 20
message_broker = None

def get_config(config_folder):
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
    if message_broker is not None:
        if message_broker.gui is not None:
            message_broker.gui.update_console(text, color)
    else:
        print(text)

def cli():
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

    audio_bytes = None
    rig_control, gui, soundcard_out = None, None, None

# If we're creating a wav file or tranmitting a message, get the symbols from the transmit_message
    if args.transmit_message:
        symbols = get_ft8_symbols(args.transmit_message)
        audio_bytes = symbols_to_audio_bytes(symbols, f_base = 900)

# If we have audio_bytes and a specified wav file, write the data to it
    if args.wave_output_file and audio_bytes:
        write_wav_file(audio_bytes, args.wave_output_file)
        console_print(f"Created wave file {args.wave_output_file}")
        sys.exit(1)

# use cases below require things from config file
    config_folder = f"{args.config_folder}".strip()
    config = get_config(config_folder)
    myCall, myGrid = config['station']['call'], config['station']['grid']
    
    if args.parse_all_file:
        history = History(config_folder, myCall)
        history.load_hearing_heard_from_all_file(config['bands'])
        history.hearing_me.save()
        history.heard_by_me.save()
        print("All file parsed and saved to hearing_me / heard_by_me files")
        sys.exit(1)

    if config.has_section('launch'):
        os.system(config['launch']['app'])

    if config.has_section('hamlib_rig'):
        console_print("Connecting to rig via Hamlib")
        rig_control = Rig_hamlib(config)
    else:
        console_print("Connecting to rig via CAT")
        rig_control = Rig_CAT(config)

    if rig_control and args.outputcard_keywords:
        soundcard_out = SoundcardOut(args.outputcard_keywords)
        if soundcard_out is None:
            time_utils.tlog(f"[Audio] No input audio device found matching {output_device_keywords}", verbose = True)
            sys.exit(1)
        
# If we have audio_bytes and capability to transmit, transmit
# (if we're just setting up for receiving or transceiving, we won't have audio_bytes)
    if soundcard_out and audio_bytes:
        rig_control.ptt_on()
        soundcard_out.send_bytes(audio_bytes)
        rig_control.ptt_off()
        sys.exit(1)

# Set up for receiving with or without Gui
    global message_broker
    message_broker = Broker()
    message_broker.rx = Receiver(message_broker, [100, 3000], args.inputcard_keywords, wav_files = None, 
                                  sync_score_min = 90, max_cands = 100, search_timerange = [-1, 3.5])
    if not message_broker.rx.audio_in.input_device_idx:
        time_utils.tlog(f"[Audio] No input audio device found matching {input_device_keywords}", verbose = True)
        sys.exit(1)

# Initialise the gui
    if not args.no_gui:
        message_broker.myCall, message_broker.myGrid = myCall, myGrid
        message_broker.soundcard_out = soundcard_out
        message_broker.adif_logging = ADIF(f"{config_folder}/PyFT8.adi")
        message_broker.history = History(config_folder, myCall, myGrid, config['gui']['loc'])
        configured_bands = {}
        for b, f in config['bands'].items():
            configured_bands[b] = f
        message_broker.gui = Gui(message_broker, rig_control, console_print,  configured_bands)
        qso_manager = QSO_manager(message_broker, rig_control, console_print)
        message_broker.gui.register_qso_manager(qso_manager)
        message_broker.rx.register_before_search(message_broker.gui.before_search)
        message_broker.rx.register_after_search(message_broker.gui.after_search)
        message_broker.history.incorporate_log_data(qso_manager.adif_logging.cache)
        message_broker.history.start_collect_new()

# Start pskreporter upload
    if myCall is not None and 'pskreporter' in config.keys():
        if config['pskreporter']['upload'] == 'Y':
            message_broker.pskr_upload = PSKR_upload(myCall, myGrid, software = f"PyFT8 v{VER}", console_print = console_print) 

# wait or show gui as appropriate
    if message_broker.gui is None:
        try:
            while True:
                time_utils.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        message_broker.gui.set_bandstats_title(f"Pskreporter Spots\nto/from {config['station']['grid'][:4]} <{PSKR_REFRESH_MINS:.0f} mins")
        message_broker.gui.main_loop()



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
