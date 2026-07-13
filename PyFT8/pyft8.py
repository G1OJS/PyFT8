import argparse
import queue, threading
import time, sys, os
from PyFT8.receiver import Receiver
from PyFT8.pskreporter import PSKR_upload
from PyFT8.gui import Gui
from PyFT8.transmitter import get_ft8_symbols, symbols_to_audio_bytes, write_wav_file, SoundcardOut
from PyFT8.time_utils import time_utils
from PyFT8.rigctrl import Rig_hamlib, Rig_CAT
from PyFT8.databases import History, ADIF
from PyFT8.qso_manager import QSO_manager

VER = '3.3.0'
PSKR_REFRESH_MINS = 20
HEARING_PANEL_LIFE_MINS = 20

gui, history, qso_manager, adif_logging, pskr_upload, soundcard_out, rig, output_device_idx = None, None, None, None, None, None, None, None
myCall, myGrid = None, None
decode_queue_non_time_critical = queue.Queue()
display_queue_batch = []
last_batch_sent = 0

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

def on_decode(c):
    global display_queue_batch, decode_queue_non_time_critical, last_batch_sent
    t = time_utils.time()
    screen_format = f"{c.cyclestart['string']} {c.snr:+03d} {c.dt:4.1f} {c.fHz:4.0f} ~ {' '.join(c.msg_tuple)}"
    print(f"{screen_format:50s} decoded@ {c.decode_completed % 15:5.1f}s")
    if gui:
        gui.enqueue_message_essentials(c)
    decode_queue_non_time_critical.put(c)

def on_decode_non_time_critical():
    while True:
        time_utils.sleep(0.5)
        band_info = qso_manager.get_band_info() if qso_manager else {'current_band': None, 'fMHz':0, 'time_set':0}
        while not decode_queue_non_time_critical.empty():
            time_utils.sleep(0.05)
            c = decode_queue_non_time_critical.get()
            if c.msg_tuple[1] != 'not':
                if gui:
                    gui.enqueue_message_updates(c)
                if history:
                    history.write_all_txt_row(c.cyclestart['string'], float(band_info['fMHz']), 'Rx', 'FT8', c.snr, c.dt, c.fHz, ' '.join(c.msg_tuple))
                    history.add_myspots_record(history.heard_by_me.data, history.heard_by_me_new, band_info['current_band'], c.msg_tuple[1], int(time_utils.time()), c.snr)
                    if c.msg_tuple[1] == myCall:
                        rpt = c.msg_tuple[2][-3:]
                        if rpt.isnumeric():
                            history.add_myspots_record(history.hearing_me.data, history.hearing_me_new, band_info['current_band'], c.msg_tuple[0], int(time_utils.time()), int(rpt))
                if pskr_upload:
                    if band_info['current_band']:
                        if c.msg_tuple[1] != myCall:
                            pskr_upload.add_report(c.msg_tuple[1], int(1000000*float(band_info['fMHz'])) + c.fHz, c.snr, 'FT8', 1, int(time_utils.time()))
     

def cli():
    global rx, gui, qso_manager, myCall, myGrid, history, adif_logging, pskr_upload, soundcard_out, rig, output_device_idx
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

# Use cases not needing sound in or out
    audio_bytes = None

    if args.parse_all_file:
        history = History(config_folder, mc, mg, PSKR_REFRESH_MINS)
        history.load_hearing_heard_from_all_file(config['bands'])
        history.hearing_me.save()
        history.heard_by_me.save()
        print("All file parsed and saved to hearing_me / heard_by_me files")
        sys.exit(1)

# If we're creating a wav file or tranmitting a message, get the symbols from the transmit_message
    if args.transmit_message:
        symbols = get_ft8_symbols(args.transmit_message)
        audio_bytes = symbols_to_audio_bytes(symbols, f_base = 900)

# If we have audio_bytes and a specified wav file, write the data to it
    if args.wave_output_file and audio_bytes:
        write_wav_file(audio_bytes, args.wave_output_file)
        console_print(f"Created wave file {args.wave_output_file}")
        sys.exit(1)

# Set up for transmitting via sound card (now we need the config file to specify rig etc)
    config_folder = f"{args.config_folder}".strip()
    config = get_config(config_folder)
    myCall, myGrid = config['station']['call'], config['station']['grid']

    if config.has_section('launch'):
        os.system(config['launch']['app'])

    if args.outputcard_keywords:
        soundcard_out = SoundcardOut(args.outputcard_keywords)

    if config.has_section('hamlib_rig'):
        console_print("Connecting to rig via Hamlib")
        rig = Rig_hamlib(config)
    else:
        console_print("Connecting to rig via CAT")
        rig = Rig_CAT(config)

# If we have audio_bytes and capability to transmit, transmit
# (if we're just setting up for receiving or transceiving, we won't have audio_bytes)
    if soundcard_out:
        if soundcard_out.output_device_index and rig and audio_bytes:
            rig.ptt_on()
            soundcard_out.send_bytes(audio_bytes)
            rig.ptt_off()
            sys.exit(1)

# Set up for receiving with or without Gui
    rx = Receiver([100, 3000], args.inputcard_keywords, wav_files = None, on_decode = on_decode,
                sync_score_min = 110, max_cands = 100, main_demap_start = 12)

# Initialise the gui
    if not args.no_gui:
        adif_logging = ADIF(f"{config_folder}/PyFT8.adi")
        qso_manager = QSO_manager(myCall, myGrid, console_print, soundcard_out.transmit_audio_data_bytes, rig, rx.audio_in.waterfall_data, adif_logging)
        history = History(config_folder, myCall, myGrid, PSKR_REFRESH_MINS)
        gui = Gui(config, qso_manager.on_click, history, console_print, qso_manager.get_band_info, rx.audio_in.waterfall_data)
        rx.register_presearch_cb(gui.clear_message_boxes)
        history.incorporate_log_data(adif_logging.cache)
        history.start_collect_new()

# Start pskreporter upload
    if myCall is not None and 'pskreporter' in config.keys():
        if config['pskreporter']['upload'] == 'Y':
            pskr_upload = PSKR_upload(myCall, myGrid, software = f"PyFT8 v{VER}", console_print = console_print) if not myCall is None else None

# Start on_decode_non_time_critical
    threading.Thread(target = on_decode_non_time_critical, daemon = True).start()

# wait or show gui as appropriate
    if gui is None:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
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
