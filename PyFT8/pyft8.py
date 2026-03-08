import argparse
import time
import os
import threading
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.gui import Gui
from PyFT8.transmitter import AudioOut
from PyFT8.time_utils import global_time_utils

MAX_TX_START_SECONDS = 2.5

def load_rigctrl():
    try:
        from Rigctrl.rig import Rig
        print("Loaded Rig control")
        return Rig()
    except ImportError:
        print("No Rig control found")
        return None
        
def get_config(configfile = 'PyFT8.pkl'):
    import pickle
    global config
    if os.path.exists(configfile):
        with open(configfile, 'rb') as f:
            config = pickle.load(f)
    else:
        c = input("Please enter your callsign ")
        g = input("Please enter your level 4 grid square ")
        config = {'mStation': {'c':c, 'g':g}}
        with open(configfile, 'wb') as f:
            pickle.dump(config, f)

class FT8_QSO:
    def __init__(self):
        self.mStation = config['mStation']
        self.band_info = {'b':'20m', 'f':14.074}
       # self.start()

    def start(self):
        self.oStation = {'c':None, 'g':None}
        self.times = {'time_on':None, 'time_off':None}
        self.rpts = {'sent': None, 'rcvd': None}
        
    def log_to_adif(self, logfile = "PyFT8.adi"):
        log_dict = {'call':self.oStation['c'], 'gridsquare':self.oStation['g'], 'mode':'FT8',
        'operator':self.mStation['c'], 'station_callsign':self.mStation['c'], 'my_gridsquare':self.mStation['g'], 
        'rst_sent':self.rpts['sent'], 'rst_rcvd':self.rpts['rcvd'], 
        'qso_date':time.strftime("%Y%m%d", self.times['time_on']), 'qso_date_off':time.strftime("%Y%m%d", self.times['time_off']),
        'time_on':time.strftime("%H%M%S", self.times['time_on']), 'time_off':time.strftime("%H%M%S", self.times['time_on']),
        'band':self.band_info['b'], 'freq':self.band_info['f']}
        if(not os.path.exists(logfile)):
            with open(logfile, 'w') as f:
                f.write("header <eoh>")
        with open(logfile,'a') as f:
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
    my_station = config['mStation']
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
    print(f"Created wave file {args.wave_output_file}")    

def transmit_threaded(msg): # move to transmitter.py?
    threading.Thread(target = transmit, args = (msg,), daemon = True).start()

def transmit(msg): # move to transmitter.py?
    if output_device_idx is None:
        print("No output device")
        return
    print(f"Transmit {msg}")
    symbols = audio_out.create_ft8_symbols(msg)
    audio_data = audio_out.create_ft8_wave(symbols)
    ct = global_time_utils.cycle_time()
    if ct > MAX_TX_START_SECONDS:
        delay = 15 - ct
        time.sleep(delay)
    print("Transmitting")
    rig.ptt_on()
    audio_out.play_data_to_soundcard(audio_data, output_device_idx)
    rig.ptt_off()
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

def on_control_click(btn_widg):
    btn_text, btn_data = btn_widg.label.get_text(), btn_widg.data
    if btn_text == "CQ":
        mc, mg = config['mStation']['c'], config['mStation']['g']
        transmit_threaded(f"CQ {mc} {mg}")
    if btn_text == "Tx off":
        rig.ptt_off()
      #      gui.post_decode((10, 50, "G1OJS G1OJY +05", (10, global_time_utils.cyclestart_time(time.time())))) # generate test message to reply to
    if('m' in btn_text):
        qso.band_info = {'b':btn_text, 'f':btn_data}
        rig.set_freq_Hz(int(1000000*qso.band_info['f']))

def on_msg_click(clicked_msg, msg_params):
    progress_qso(clicked_msg, msg_params)

#=============== CLI ========================================================================        
def cli():
    global audio_in, audio_out, output_device_idx, rig, gui, qso
    import time
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')    
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device')
    parser.add_argument('-n','--no_gui',  action='store_true',  help = 'Dont create a gui')
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8.wav')
    args = parser.parse_args()

    output_device_idx = None
    gui = None
    if args.outputcard_keywords:
        outputcard_keywords = args.outputcard_keywords.replace(' ','').split(',')
        audio_out = AudioOut()
        output_device_idx = audio_out.find_device(outputcard_keywords)
        get_config()
        rig = load_rigctrl()
            
    if args.transmit_message:
        if not transmit(args.transmit_message):
            make_wav(args.transmit_message, args.wave_output_file)      
    else:
        audio_in = AudioIn(3100)
        input_device_idx = audio_in.find_device(args.inputcard_keywords.replace(' ','').split(','))
        if not input_device_idx:
            print("No input device")
        else:
            gui = None if args.no_gui else Gui(audio_in.dBgrid_main, 4, 2, config['mStation'], on_msg_click, on_control_click)
            rx = Receiver(audio_in, [200, 3100], on_decode)
            audio_in.start_streamed_audio(input_device_idx)
            if gui is not None:
                if output_device_idx:
                    qso = FT8_QSO()
                gui.plt.show()
            else:
                wait_for_keyboard()


#================== TEST CODE ============================================================
print(__name__)
if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC']):
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC']):
        cli()
