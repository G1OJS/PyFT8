import argparse
import time
import os
import threading
import pickle
import numpy as np
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.pskr_upload import PSKR_upload
from PyFT8.gui import Gui
from PyFT8.transmitter import AudioOut
from PyFT8.time_utils import global_time_utils
from PyFT8.rigctrl import Rig
from PyFT8.hamlib import Rig_hamlib
from PyFT8.mqtt import PSKR_MQTT_listener
import PyFT8.maidenhead as maidenhead

VER = '2.6.2'

MAX_TX_START_SECONDS = 2.5
rig, gui, qso, adif_logging, pskr_info, pskr_upload = None, None, None, None, None, None
busy_profile, hearing_me = None, None

def get_config():
    import configparser
    global config
    config = configparser.ConfigParser()
    ini_file = f"{config_folder}/PyFT8.ini"
    if not os.path.exists(ini_file):
        config['station'] = {'call':'station_callsign', 'grid':'station_grid'}
        config['bands'] = {'20m':14.074}
        config['hamlib_rig'] = {'rigctld':'C:/WSJT/wsjtx/bin/rigctld-wsjtx', 'port': 'COM4', 'baud_rate':9600, 'model':3070}
        config['rig'] = {'port': 'COM4', 'baud_rate':9600,
                         'set_freq_command':'FEFE88E0.05.0000000000.FD', 'set_freq_value':'5|5|vfBcdLU|1|0',
                         'ptt_on_command':'FEFE88E0.1C00.01.FD', 'ptt_off_command':'FEFE88E0.1C00.00.FD'}
        config['pskreporter'] = {'upload':'N'}
        with open(ini_file, 'w') as f:
            config.write(f)
        console_print(f"Wrote default config to {ini_file}")
    console_print(f"Reading config from {ini_file}")
    config.read(ini_file)

def ensure_file_exists(path, header = None):
    try:
        with open(path, "x") as f:
            if header is not None:
                f.write(header)
    except FileExistsError:
        pass
      
class ADIF:
    def __init__(self, logfile):
        self.adif_log_file = logfile
        ensure_file_exists(self.adif_log_file, header = "header <eoh>\n")
        console_print(f"ADIF to {self.adif_log_file}")
        self.cache = self._build_cache()
              
    def log(self, times, band_info, mStation, oStation, rpts):
        log_dict = {'call':oStation['c'], 'gridsquare':oStation['g'], 'mode':'FT8',
        'operator':mStation['c'], 'station_callsign':mStation['c'], 'my_gridsquare':mStation['g'], 
        'rst_sent':rpts['sent'], 'rst_rcvd':rpts['rcvd'], 
        'qso_date':time.strftime("%Y%m%d", times['time_on']), 'qso_date_off':time.strftime("%Y%m%d", times['time_off']),
        'time_on':time.strftime("%H%M%S", times['time_on']), 'time_off':time.strftime("%H%M%S", times['time_on']),
        'band':band_info['b'], 'freq':band_info['fMHz']}
        with open(self.adif_log_file,'a') as f:
            for k, v in log_dict.items():
                v = str(v)
                f.write(f"<{k}:{len(v)}>{v} ")
            f.write(f"<eor>\n")
        cbm = log_dict['call'] + "_" + log_dict['band'] + "_FT8"
        tm = time.time()
        self.cache[log_dict['call']] = tm
        self.cache[cbm] = tm
        console_print(f"Logged QSO with {oStation['c']}")

    def _build_cache(self):
        import datetime
        def parse(rec, field):
            p = rec.find(field)
            if p > 0:
                p1, p2 = rec.find(':',p), rec.find('>',p)
                n = int(rec[p1+1:p2])
                return rec[p2+1: p2+1+n]
        cache = {}
        with open(self.adif_log_file, 'r') as f:
            for l in f.readlines():
                if parse(l, 'mode') == "FT8":
                    c, b, d, t = parse(l, 'call'), parse(l, 'band'), parse(l, 'qso_date'), parse(l, 'time_on')
                    tm = time.mktime(datetime.datetime.strptime(d+t, "%Y%m%d%H%M%S").timetuple())
                    cache[c] = tm
                    cache[c + "_"+b+"_FT8"] = tm
        return cache

def get_geo_text(call):
    geo_text = ''
    loc = pskr_info.callsign_cache.data.get(call,'')
    if loc and config['gui']['loc'] == 'km_deg':
            loc = maidenhead.db(config['station']['grid'], loc)
            geo_text = f"{int(loc[0]):5d}k {int(loc[1]):3d}°"
    if loc and config['gui']['loc'] == 'loc':
            geo_text = f"loc: {loc}"
    return geo_text

class Message:
    def __init__(self, candidate):
        c = candidate
        mycall = ''
        if qso is not None:
            mycall = qso.mStation['c']
        self.h0_idx, self.f0_idx, self.msg_tuple, self.msg, self.snr, self.dt, self.fHz = c.h0_idx, c.f0_idx, c.msg_tuple, c.msg, c.snr, c.dt, c.fHz
        self.cyclestart = c.cyclestart
        self.expire = time.time() + 29.8
        self.is_from_me = c.msg_tuple[1] == mycall
        self.is_to_me = c.msg_tuple[0] == mycall
        self.is_cq = c.msg_tuple[0].startswith('CQ')
        geo_text = get_geo_text(c.msg_tuple[1])
        wb_time = adif_logging.cache.get(c.msg_tuple[1],'')
        wb_text = f"wb: {global_time_utils.format_duration(time.time() - float(wb_time))}" if wb else ''
        self.gui_text = f"{c.msg} {wb_text} {geo_text}"
    
    def wsjtx_screen_format(self):
        return f"{self.cyclestart['string']} {self.snr:+03d} {self.dt:4.1f} {self.fHz:4.0f} ~ {self.msg}"

    def wsjtx_all_txt_format(self):
        fMHz = float(qso.band_info['fMHz']) if qso.band_info['fMHz'] is not None else 0
        return f"{self.cyclestart['string']} {fMHz:8.3f} Rx FT8    {self.snr:+03d} {self.dt:4.1f} {self.fHz:4.0f} ~ {self.msg}"

class FT8_QSO:
    def __init__(self):
        if config is not None:
            self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.band_info = {'b':None, 'fMHz':0}
        self.tx_freq = 750
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
        if gui and self.band_info['b'] is None:
            console_print("[PyFT8] Please select a band before transmitting", color = 'red')
            return
        console_print(f"[QSO] Set transmit message to '{message}' with tx cycle = {self.tx_cycle}")
        self.message_to_transmit = message

    def _transmitter(self):
        while True:
            time.sleep(0.1)
            if self.message_to_transmit is None:
                continue
            if output_device_idx is None:
                console_print("No output device")
                return
            ct = global_time_utils.cycle_time()
            if ct > MAX_TX_START_SECONDS:
                delay = 15.25 - ct
                time.sleep(delay)
            if self.tx_cycle is None:
                self.tx_cycle = global_time_utils.curr_cycle_from_time()
                self.tx_freq = clearest_frequency
                console_print(f"[PyFT8] Set tx cycle = {self.tx_cycle} f = {self.tx_freq:5.1f}")
            symbols = audio_out.create_ft8_symbols(self.message_to_transmit)
            if any(symbols):
                console_print(f"Transmitting {self.message_to_transmit} on cycle {self.tx_cycle}")
                audio_data = audio_out.create_ft8_wave(symbols, f_base = self.tx_freq)
                rig.ptt_on()
                audio_out.play_data_to_soundcard(audio_data, output_device_idx)
                rig.ptt_off()
                self.last_tx = self.message_to_transmit
            else:
                console_print(f"Couldn't encode message {self.message_to_transmit}", color = 'red') # move this to earlier by setting tx symbols not tx message
            self.message_to_transmit = None

    def log(self):
        if adif_logging is not None:
            self.times['time_off'] = time.gmtime()
            adif_logging.log(self.times, self.band_info, self.mStation, self.oStation, self.rpts)

def isReport(grid_rpt):     return "+" in grid_rpt or "-" in grid_rpt
def isRReport(grid_rpt):    return isReport(grid_rpt) and 'R' in grid_rpt
def isRRR(grid_rpt):        return 'RRR' in grid_rpt
def isRR73(grid_rpt):       return 'RR73' in grid_rpt
def is73(grid_rpt):         return '73' in grid_rpt and not isRR73(grid_rpt)
def isGrid(grid_rpt):       return not isReport(grid_rpt) and not is73(grid_rpt) and not isRR73(grid_rpt) and not isRRR(grid_rpt) 

def progress_qso(clicked_message):
    global qso
    
    if time.time() - clicked_message.cyclestart['time'] > (15 + MAX_TX_START_SECONDS):
        console_print("Try next cycle")
        return
    
    call_a, call_b, grid_rpt = clicked_message.msg_tuple
    my_station = qso.mStation
    reply = ""
    msg = ' '.join(clicked_message.msg_tuple)
    console_print(f"[QSO] Clicked on message '{msg}'")

    if call_a == "CQ":
        qso.clear()
        qso.times['time_on'] = time.gmtime()
        qso.oStation = {'c': call_b, 'g': grid_rpt}
        qso.rpts['sent'] = f"{clicked_message.snr:+03d}"
        qso.set_tx_message(f"{qso.oStation['c']} {my_station['c']} {my_station['g'][:4]}")
        return

    if call_a == my_station['c']:
        if qso.times['time_on'] is None:
            qso.times['time_on'] = time.gmtime()
        if qso.rpts['sent'] is None:
            qso.rpts['sent'] = f"{clicked_message.snr:+03d}"
        qso.oStation['c'] = call_b
        if isGrid(grid_rpt):
            qso.oStation = {'c': call_b, 'g': grid_rpt}
            reply = f"{qso.oStation['c']} {my_station['c']} {clicked_message.snr:+03d}"
        if isReport(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} R{clicked_message.snr:+03d}"
            qso.rpts['rcvd'] = grid_rpt[-3:]
        if isRReport(grid_rpt) or isRRR(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} RR73"
            qso.log()
        if isRR73(grid_rpt):
            reply = f"{qso.oStation['c']} {my_station['c']} 73"
            qso.log()
        qso.set_tx_message(reply)

def make_wav(msg, wave_output_file): # move to transmitter.py?
    symbols = audio_out.create_ft8_symbols(msg)
    audio_data = audio_out.create_ft8_wave(symbols)
    audio_out.write_to_wave_file(audio_data, wave_output_file)
    console_print(f"Created wave file {wave_output_file}")

def wait_for_keyboard():
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

def write_all_txt_row(message):
    all_file = f"{config_folder}/ALL.txt"
    mode = 'w' if not os.path.exists(all_file) else 'a'
    row = message.wsjtx_all_txt_format()
    with open(all_file, mode) as f:
        f.write(f"{row}\n")

#============= Callbacks for Receiver ==========================================================
def on_rx_decode(c):
    message = Message(c)
    if gui:
        gui.add_message_box(message)
    if qso.band_info['b'] is not None and pskr_upload is not None:
        dx_call = c.msg_tuple[1]
        if dx_call != 'not' and dx_call != config['station']['call']:
            pskr_upload.add_report(dx_call, int(1000000*float(qso.band_info['fMHz'])) + c.fHz, c.snr, 'FT8', 1, int(time.time()))
    print(message.wsjtx_screen_format())
    write_all_txt_row(message)

def on_rx_busy_profile(busy_profile_new, cycle):
    global busy_profile
    if output_device_idx is None:
        return
    if busy_profile is not None:
        busy_profile += busy_profile_new
        fmax = 950 if qso.band_info['b']=='60m' else 2000
        f0_idx, fn_idx = int(500/audio_in.df), int(fmax/audio_in.df)
        idx = np.argmin(busy_profile[f0_idx:fn_idx])
        clearest_frequency = (f0_idx + idx) * audio_in.df
    busy_profile = busy_profile_new
    #console_print(f"[on_busy] Set Tx freq to {clearest_frequency:6.1f}")

#============= Callbacks for GUI ==========================================================
def on_gui_sidebars_refresh(gui):
    if qso.band_info['b'] is None:
        console_print(f"[PyFT8] Band not set; please select a band.", color = 'red')
    if pskr_info is None:
        return
    
    # refresh band stats
    grd = config['station']['grid'][:4]
    for bb in gui.button_boxes:
        band = bb.clickargs.get('band','')
        if band:
            bb.set_active(band == qso.band_info.get('b',''))
            if band in pskr_info.home_activity:
                cnts = pskr_info.home_activity[band]
                new_text = f"{cnts[0]}Tx, {cnts[1]}Rx"
                if new_text != bb.get_info_text():
                    bb.set_info_text(new_text)

    # refresh home square counts
    b = qso.band_info['b']
    if b is not None and b in pskr_info.home_most_remotes:
        tx_lead,  rx_lead = pskr_info.home_most_remotes[b]
        call = config['station']['call']
        n_spotted, n_spotting = pskr_info.get_spot_counts(b, call)
        # add local count here for n_spotted prior to round trip to pskreporter?
        gui.band_stats.scroll_print(f"{call:<7} {tx_lead[0]:<7}", color = '#ff756b')
        gui.band_stats.scroll_print(f"{n_spotting:<7} {tx_lead[1]:<7}", color = '#ff756b')
        gui.band_stats.scroll_print(f"{call:<7} {rx_lead[0]:<7}", color = '#b6f0c6')
        gui.band_stats.scroll_print(f"{n_spotted:<7} {rx_lead[1]:<7}", color = '#b6f0c6')

    #refresh hearing me
    if b is not None and b in pskr_info.hearing_me.data:
        hearing_me_text = []
        for h in pskr_info.hearing_me.data[b].values():
            geo_text = geo_text = get_geo_text(h['c'])
            hearing_me_text.append(f"{h['c']:<7} {int(h['rp']):+03d} {geo_text:<12}")
        gui.hm.list_print(hearing_me_text)

def on_gui_control_click(btn_def):
    btn_action = btn_def['action']
    if btn_action == "CQ":
        mc, mg = config['station']['call'], config['station']['grid'][:4]
        qso.set_tx_message(f"CQ {mc} {mg}")
    if btn_action == "RPT_LAST":
        qso.set_tx_message(qso.last_tx)
    if btn_action == "TX_OFF":
        console_print("[PyFT8] Set PTT Off")
        rig.ptt_off()
        qso.tx_cycle = None
    if(btn_action == 'SET_BAND'):
        band, freqMHz = btn_def['band'], btn_def['freq']
        qso.band_info = {'b':band, 'fMHz':freqMHz}
        rig.set_freq_Hz(int(1000000*float(qso.band_info['fMHz'])))
        console_print(f"[PyFT8] Set band: {qso.band_info['b']} {qso.band_info['fMHz']}")
        gui.band_stats.clear()
        gui.refresh_sidebars()
        
def on_gui_msg_click(message):
    progress_qso(message)

#=============== CLI ========================================================================
def console_print(text, color = 'white'):
    if gui is not None:
        gui.console.scroll_print(text, color)
    else:
        print(text)
        
def cli():
    global audio_in, audio_out, output_device_idx, rig, gui, qso, config, config_folder, clearest_frequency, adif_logging, pskr_upload, pskr_info
    import time
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-c', '--config_folder', help = 'Location of config folder e.g. C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg', default = './') 
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    #parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')    
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device')
    parser.add_argument('-n','--no_gui',  action='store_true',  help = "Don't create a gui")
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file name', default = 'PyFT8.wav')
    args = parser.parse_args()

    output_device_idx = None
    config_folder = f"{args.config_folder}".strip()
    get_config()
    adif_logging = ADIF(f"{config_folder}/PyFT8.adi")
    mc, mg = config['station']['call'], config['station']['grid']
    if mc is not None and 'pskreporter' in config.keys():
        if config['pskreporter']['upload'] == 'Y':
            pskr_upload = PSKR_upload(mc, mg, software = f"PyFT8 v{VER}", console_print = console_print) if not mc is None else None
            pskr_info = PSKR_MQTT_listener(config_folder, mc, mg[:4])
    qso = FT8_QSO()
    if config.has_section('hamlib_rig'):
        console_print("Connecting to rig via Hamlib")
        rig = Rig_hamlib(config)
    else:
        console_print("Connecting to rig via CAT")
        rig = Rig(config)

    if args.transmit_message or args.outputcard_keywords:
        audio_out = AudioOut()
        clearest_frequency = 760
    
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
            console_print("No input device")
        else:
            gui = None if args.no_gui else Gui(audio_in.dBgrid_main, 4, 2, config, on_gui_sidebars_refresh, on_gui_msg_click, on_gui_control_click)
            rx = Receiver(audio_in, [200, 3100], on_rx_decode, on_rx_busy_profile)
            audio_in.start_streamed_audio(input_device_idx)
            if gui is not None:
                gui.plt.show()
            else:
                wait_for_keyboard()


#================== TEST CODE ============================================================
if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC', '-c C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-n']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-cC:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg']):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90", '-o', "Speak, CODEC"]):
    #with mock.patch('sys.argv', ['pyft8', '-m',  "CQ G1OJS IO90"]):
        cli()
