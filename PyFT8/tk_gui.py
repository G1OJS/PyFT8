import tkinter as tk
import time, threading, struct, random, json, os, queue, sys, subprocess
import configparser
import numpy as np
import paho.mqtt.client as mqtt
from ast import literal_eval
from PyFT8.receiver import Receiver
from PyFT8.transmitter import Transmitter
from PyFT8.udp_comms import UdpComms

VERSION = "4.0.4"
PORTS = {'gui_to_rx': 2121, 'rx_to_gui':2122, 'gui_to_tx': 2123, 'tx_to_gui': 2124}
HEARING_ME_WINDOW_SECS = 300
MAX_CYCLETIME_TX_START = 3
MAX_PSKR_REPORTS = 90
T_CYC, TX_T0 = 15, 0.3

class HearingMe:
    def __init__(self, my_call, my_grid):
        self.hearing_me = []
        self.my_call = my_call
        client_id = "pyft8_" + ''.join(random.choice('0123456789ABCDEF') for i in range(16))
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
        mqttc._on_connect = lambda c,u,f,r,p: c.subscribe(f"pskr/filter/v2/+/FT8/+/+/{my_grid}/#")
        mqttc._on_message = lambda c,u,m: self._process_message(m)
        mqttc.connect("mqtt.pskreporter.info", 1883, 60)
        threading.Thread(target = mqttc.loop_forever, daemon = True).start()
        threading.Thread(target = self._housekeep, daemon = True).start()

    def _process_message(self, m):
        try:
            self.hearing_me.append(literal_eval(m.payload.decode()))
        except:
            pass
                               
    def _housekeep(self):
        while True:
            time.sleep(5)
            delete = [e for e in self.hearing_me if time.time() - int(e['t']) > HEARING_ME_WINDOW_SECS]
            for d in delete:
                self.hearing_me.remove(d)

    def is_hearing_me(self, band_tuple, their_call):
        return any([c for c in self.calls_hearing_my_call(band_tuple) if c == their_call])

    def calls_hearing_my_call(self, band_tuple):
        return [m['rc'] for m in self.hearing_me if m['b'] == band_tuple[0] and m['sc'] == self.my_call]

    def calls_hearing_my_grid(self, band_tuple):
        return [m['rc'] for m in self.hearing_me if m['b'] == band_tuple[0]]

    def compress_report(self, hm):
        hm = [c[:2] for c in hm] if len(hm) > 10 else hm
        hm = list(set(hm))
        hm.sort()
        return hm


class PSKR_upload:
    # https://pskreporter.info/pskdev.html
    # https://pskreporter.info/cgi-bin/psk-analysis.pl
    def __init__(self, mycall, mygrid, software, pskr_addr = {'host':'report.pskreporter.info', 'port':4739}):
        self.udp_comms_pskr = UdpComms(ports = {'listen':None, 'send':pskr_addr['port']}, remote_host = pskr_addr['host'])
        self.RxInfoRecDescriptor_CallLocSoft = b"\x00\x03\x00\x24\x99\x92\x00\x03\x00\x01\x80\x02\xFF\xFF\x00\x00\x76\x8F\x80\x04\xFF\xFF\x00\x00\x76\x8F\x80\x08\xFF\xFF\x00\x00\x76\x8F\x00\x00"
        self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime = b"\x00\x02\x00\x3C\x99\x93\x00\x07\x80\x01\xFF\xFF\x00\x00\x76\x8F\x80\x05\x00\x04\x00\x00\x76\x8F\x80\x06\x00\x01\x00\x00\x76\x8F\x80\x07\x00\x01\x00\x00\x76\x8F\x80\x0A\xFF\xFF\x00\x00\x76\x8F\x80\x0B\x00\x01\x00\x00\x76\x8F\x00\x96\x00\x04"
        self.last_descriptors_time = 0
        self.descriptors_sent_count = 0
        self.last_report_time = time.time() - 300 + 60
        self.session_id = random.getrandbits(32)
        self.seq = 1
        self.reports = {}
        rx = self._enc_str(mycall) + self._enc_str(mygrid) + self._enc_str(software)
        self.rx_block =  self._block(b"\x99\x92", rx)
        self.lock = threading.Lock()

    def add_report(self, band_tuple, msg_dict):
        if band_tuple is not None:
            band, fHz_dial = band_tuple
            their_snr, freq_hz = int(msg_dict['their_snr']), fHz_dial + float(msg_dict['fHz'])
            dxcall, mode = msg_dict['msg_tuple'][1], "FT8"
            source, tt = 1, int(time.time())
            with self.lock:
                self.reports[dxcall] = (dxcall, freq_hz, their_snr, mode, source, (tt // 15) * 15)

    def _enc_str(self, s):
        b = s.encode("ascii")
        return struct.pack("B", len(b)) + b

    def _block(self, block_type, payload):
        len_with_header = len(payload) + 4
        pad_len = (4 - (len_with_header % 4)) % 4
        len_with_pad = len_with_header + pad_len
        blk = block_type + struct.pack("!H", len_with_pad) + payload + b"\x00" * pad_len
        return blk 

    def send_reports(self):
        with self.lock:
            if len(self.reports) >= MAX_PSKR_REPORTS or (time.time() - self.last_report_time) > 300:
                if (time.time() - self.last_descriptors_time) > 3600:
                    self.descriptors_sent_count = 0
                    self.last_descriptors_time = time.time()
                self._send(includeDescriptors = (self.descriptors_sent_count <4))
                self.descriptors_sent_count +=1
           
    def _send(self, includeDescriptors = False):
        if not self.reports:
            return
        tt = int(time.time())
        ipfx_header = struct.pack("!H", 10) + b"\x00\x00" + struct.pack("!I", tt) + struct.pack("!I", self.seq) + struct.pack("!I", self.session_id)
        header = ipfx_header
        if includeDescriptors:
            header = header + self.RxInfoRecDescriptor_CallLocSoft + self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime
        senders = bytearray()
        for dxcall, freq_hz, snr, mode, source, tt in self.reports.values():
            sender = self._enc_str(dxcall) + struct.pack("!I", int(freq_hz)) + struct.pack("b", int(snr)) + struct.pack("b", 0) + self._enc_str(mode) + struct.pack("B", source) + struct.pack("!I", tt)
            senders += sender
        packet = bytearray(header + self.rx_block + self._block(b"\x99\x93", senders))
        struct.pack_into("!H", packet, 2, len(packet))
        self.seq += len(self.reports)
        self.udp_comms_pskr.udp_send_bytes(packet)
        self.reports = {}
        self.last_report_time = time.time()


class ADIF:
    def __init__(self, logfile):
        self.adif_log_file = logfile
        if not os.path.exists(self.adif_log_file):
            with open(self.adif_log_file, 'w') as f:
                f.write("header <eoh>\n")
        self.cache = self._build_cache()
              
    def log(self, band_tuple, qso_dict):
        gmt = time.gmtime()
        qd = qso_dict
        if band_tuple is not None:
            band, fHz_dial = band_tuple
            freq = f"{ (float(fHz_dial) + float(qd['fHz']))/1e6 : .3f}"
            log_dict = {'operator':qd['call'], 'station_callsign':qd['call'], 'my_gridsquare':qd['grid'], 'mode':'FT8',
                        'time_on': time.strftime("%H%M%S", gmt), 'qso_date':time.strftime("%Y%m%d", gmt),
                        'band':band, 'freq': freq,
                        'call':qd['their_call'], 'gridsquare': qd['their_grid'], 'rst_sent':qd['their_snr'], 'rst_rcvd':qd['my_snr']}
            with open(self.adif_log_file,'a') as f:
                for k, v in log_dict.items():
                    v = str(v)
                    f.write(f"<{k}:{len(v)}>{v} ")
                f.write(f"<eor>\n")
            cbm = log_dict['call'] + "_" + log_dict['band'] + "_FT8"
            tm = time.time()
            self.cache[log_dict['call']] = tm
            self.cache[cbm] = tm

    def get_worked_before_info(self, their_call):
        wb_time = self.cache.get(their_call,'')
        if wb_time:
            delta_time = (time.time() - float(wb_time))
            intervals = ( ('yr', 314496000), ('wk', 604800), ('day', 86400), ('hr', 3600), ('min', 60), ('sec', 1) )
            for name, count in intervals:
                value = int(delta_time / count)
                if value:
                    return f"{value:d} {name}{'s' if value > 1 else ''}"
        return ''

    def _build_cache(self):
        import calendar, time
        def parse(rec, field):
            p = rec.find(field)
            if p<0:
                p = rec.find(field.upper())
            if p<0:
                p = rec.find(field.lower())
            if p > 0:
                p1, p2 = rec.find(':',p), rec.find('>',p)
                n = int(rec[p1+1:p2])
                return rec[p2+1: p2+1+n]
        cache = {}
        with open(self.adif_log_file, 'r') as f:
            for l in f.readlines():
                if parse(l, 'mode') == "FT8":
                    c, b, d, t = parse(l, 'call:'), parse(l, 'band'), parse(l, 'qso_date'), parse(l, 'time_on')
                    if c and b and d and t:
                        time_tuple = time.strptime(d+t, "%Y%m%d%H%M%S")
                        tm = calendar.timegm(time_tuple)
                        cache[c] = tm
                        cache[c + "_"+b+"_FT8"] = tm
        return cache

class Gui:
    def __init__(self, Receiver = None, Transmitter = None, config_folder = None,
                 config = None, band_tuples = None):
        self.config_folder = config_folder
        self.config = config
        self.band_tuples = band_tuples
        self.band_tuple = ('',0)
        self.band_changed = 0
        self.running = True
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._shutdown_all())
        self.root.resizable(0,0)
        self.root.title(f"PyFT8 {VERSION} by G1OJS")
        self._start_components()
        self._start_internals()
        self._make_layout()
        self._start()

    def _monitor_udp(self):
        if not self.udp_q.empty():
            self._handle_udp_message(self.udp_q.get())
        if self.running:
            self.root.after(100, self._monitor_udp)

#-----------------------------------------------------------------------------------------------------
    def _start(self):
        self._do_each_second()
        self._update_pskr_uploader()
        self._send_waterfall_row()
        self._reset_qso_dict()
        self.pending_start_tx_stream = None
        self.pending_ptt_on = None
        self.last_rx_time = 0
        self.tx_cycle = None
        self._set_tx_freq(777)
        self._get_band()
        self.root.mainloop()

    def _start_components(self):
        self.component_status = {}
        self.udp_q = queue.Queue()
        self.udp_comms_rcvr = UdpComms(ports = {'listen':PORTS['rx_to_gui'], 'send':PORTS['gui_to_rx']}, rx_callback = lambda msg_dict: self.udp_q.put(msg_dict))
        self.udp_comms_txr = UdpComms(ports = {'listen':PORTS['tx_to_gui'], 'send':PORTS['gui_to_tx']}, rx_callback = lambda msg_dict: self.udp_q.put(msg_dict))
        self._monitor_udp()
        rx = Receiver(ports = {'listen':PORTS['gui_to_rx'], 'send':PORTS['rx_to_gui']}, input_keywords = self.config['soundcard']['receive'])
        tx = Transmitter(ports = {'listen':PORTS['gui_to_tx'], 'send':PORTS['tx_to_gui']}, output_keywords = self.config['soundcard']['transmit'])
        self.root.after(2000, self._check_components)

    def _start_internals(self):
        self.hearing_me = HearingMe(self.config['station']['call'], self.config['station']['grid'])
        self.pskr_upload = None
        if self.config.has_section('pskreporter'):
            if self.config['pskreporter']['upload'] == 'Y':
                self.pskr_upload = PSKR_upload(self.config['station']['call'], self.config['station']['grid'], f"PyFT8 v{VERSION}")
        self.rig_base_command = None
        if self.config.has_section('rig_control'):
            cfg_keys = ['rigctl', 'model', 'port', 'baud_rate']
            vals = [self.config['rig_control'][key] for key in cfg_keys]
            self.rig_base_command  = f"{vals[0]} -m {vals[1]} -r {vals[2]} -s {vals[3]} "
        self.adif_log = None
        if self.config.has_section('logging'):
            self.adif_log = ADIF(self.config['logging']['logfile'])
        self.last_rx_time = 0
        self.last_tx_message = None

    def _check_components(self):
        if not all([comp in self.component_status for comp in ['receiver','transmitter']]):
            self._set_footer("Transmitter or Receiver module failed to send status message", echo_to_print = True)
            self._shutdown_all()
        if not all([self.component_status[comp] == 'OK' for comp in self.component_status]):
            self._set_footer("Transmitter or Receiver module failed to send status = OK", echo_to_print = True)
            self._shutdown_all()
        else:
            self._set_footer("Transmitter and Receiver sent status = OK")
            
    def _shutdown_all(self):
        print("Shutting down")
        if self.running:
            self.running = False
        time.sleep(2)
        self.root.after(1000, self.root.destroy)
        sys.exit()
        exit()

#-----------------------------------------------------------------------------------------------------

    def _command_rig(self, cmd):
        if self.rig_base_command:
            cmd_out = self.rig_base_command + cmd
            proc = subprocess.run(cmd_out, creationflags = subprocess.CREATE_NO_WINDOW, capture_output = True)
            resp = proc.stdout.decode()
            return resp.strip()

    def _get_band(self):
        fHz = self._command_rig('f')
        if fHz:
            if fHz.isnumeric():
                fHz = int(fHz)
                matched_band_tuples = [bt for bt in self.band_tuples if abs(int(bt[1]) - fHz) < 10000]
                if len(matched_band_tuples) == 1:
                    self.band_tuple = matched_band_tuples[0]
                
    def _set_band(self, band_tuple):
        self.band_tuple = band_tuple
        self.band_changed = time.time()
        self._command_rig(f"F {band_tuple[1]}")
        self.decodes_text.delete(1.0, tk.END)

    def _set_power(self, power):
        self._command_rig(f"L RFPOWER {float(power)/100:8.6f}")

#-----------------------------------------------------------------------------------------------------

    def _make_layout(self):
        font_clk = ('calibri', 14, 'bold')
        font_msg = ('Courier', 11, 'bold')
        font_btn = ('calibri', 11, 'bold')
        self.app_container = tk.Frame(self.root)
        self.app_container.pack(side = 'top')

        self.ribbon_frame = tk.Frame(self.app_container, bg='purple', bd = 2, relief = tk.SUNKEN)
        self.ribbon_frame.pack(side = 'top', expand = True, fill = 'x')
        self.left_sidebar_container = tk.Frame(self.app_container)
        self.left_sidebar_container.pack(side = 'left', fill = 'both')

        self.right_sidebar_container = tk.Frame(self.app_container, width = 100, bg = 'orange')
        self.right_sidebar_container.pack(side = 'left', fill = 'both', anchor = 'e')
        self.hm_text = tk.Text(self.right_sidebar_container, wrap=tk.WORD, width = 12)
        self.hm_text.pack(side=tk.LEFT, fill='y', expand=True)
        self.hm_text.tag_config('me', foreground = 'blue')
        self.hm_text.insert(tk.END, "Hearing me", 'me')
        self.hm_text.insert(tk.END, "/grid\n")
        
        self.waterfall_container = tk.Frame(self.app_container)
        self.waterfall_container.pack(side = 'top', fill = 'both')
        self.decodes_header = tk.Frame(self.app_container)
        self.decodes_header.pack(side = 'top', expand = True, fill = 'x')
        self.decodes_header_txt = tk.Label(self.decodes_header, text = '', font = font_msg)
        self.decodes_header_txt.pack(side = 'left', anchor = 'w')
        self.decodes_container = tk.Frame(self.app_container) 
        self.decodes_container.pack(side = 'top')
        self.footer = tk.Frame(self.app_container, bd = 2, relief = tk.SUNKEN)
        self.footer.pack(side = 'top', expand = True, fill = 'x')
        self.footer_txt = tk.Label(self.footer, text = '', font = font_msg)
        self.footer_txt.pack(side = 'top', anchor = 'w')
        
        self.clock_lbl = tk.Label(self.ribbon_frame, font = font_clk , fg='white', bg='purple')
        self.clock_lbl.pack(expand = True, anchor = 'w', side = 'left')
        self.band_lbl = tk.Label(self.ribbon_frame, font = font_clk , fg='white', bg='purple')
        self.band_lbl.pack(expand = True, anchor = 'w', side = 'left')
        
        self.buttons = []
        bc = self.left_sidebar_container
        self.buttons.append(tk.Button(bc, width = 10, font = font_btn, text = 'CQ', command = self._call_cq))
        self.buttons.append(tk.Button(bc, width = 10, font = font_btn, text = 'Repeat last', command = self._queue_transmit))
        self.buttons.append(tk.Button(bc, width = 10, font = font_btn, text = 'STOP TX', command = self._stop_transmit))
        for btn in self.buttons:
            btn.pack(side = 'top', anchor = 'n', pady = 1)

        for band_tuple in self.band_tuples:
            band, _ = band_tuple
            btn = tk.Button(bc, width = 10, text = band, font = font_btn, command = lambda band_tuple = band_tuple: self._set_band(band_tuple))
            btn.pack(side = 'top', anchor = 'n', pady = 1)
            self.buttons.append(btn)

        if self.config.has_section('power'):
            for p, v in self.config['power'].items():
                btn = tk.Button(bc, width = 10, text = p, font = font_btn, command = lambda v = v: self._set_power(v))
                btn.pack(side = 'top', anchor = 'n', pady = 1)
                self.buttons.append(btn)
                
        self.waterfall_canvas = tk.Canvas(self.waterfall_container, height = 100, bg = '#909090')
        self.waterfall_canvas.pack(side = 'top', fill = 'both')
        self.waterfall_info_txt = self.waterfall_canvas.create_text(25,10, text='')
        self.waterfall_canvas.bind('<Button-1>', self._waterfall_click)
        self.waterfall_canvas.bind('<Motion>', self._set_waterfall_info)
        self.waterfall_canvas.bind('<Leave>', lambda e: self.waterfall_canvas.itemconfigure(self.waterfall_info_txt, text = ''))
        self.waterfall_line = self.waterfall_canvas.create_line(0,0,600,0, fill = '#40E040', width = 2)
        self.waterfall_tx_freq = self.waterfall_canvas.create_line(0,0,0,0, fill = '#E04040', width = 2)
        self.waterfall_vals = None
        self.waterfall_new_vals = None
        
        self.scrollbar = tk.Scrollbar(self.decodes_container)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.decodes_text = tk.Text(self.decodes_container, wrap=tk.WORD, yscrollcommand=self.scrollbar.set)
        self.decodes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        font=('calibri', 12, 'bold')
        self.decodes_text.tag_config('norm', foreground = 'white', background = 'blue', font = font_msg )
        self.decodes_text.tag_config('info', foreground = 'black', background = 'white', font = font_msg)
        self.decodes_text.tag_config('cq', foreground = 'white', background = 'green', font = font_msg)
        self.decodes_text.tag_config('to_me', foreground = 'white', background = 'red', font = font_msg)        
        self.decodes_text.tag_config('from_me', foreground = 'black', background = 'yellow', font = font_msg)
        self.decodes_text.tag_config('highlight', foreground = 'black', background = 'yellow', font = font_msg)
        self.decodes_text.bind('<Button-1>', self._row_click)
        self.scrollbar.config(command=self.decodes_text.yview)
        self.decodes_header_txt.config(text = self._format_display_text('SNR','dt','fHz','Message','Wkd', '@'))

#-----------------------------------------------------------------------------------------------------

    def _format_display_text(self, SNR,dt,fHz,Message,Wkd, hm):
        return f" {SNR:<3s} {dt:<5s} {fHz:<7s} | {Message:<25s} | {Wkd:<8s} {hm:<1s}"

    def _set_footer(self, info, echo_to_print = False):
        self.footer_txt.config(text = info)
        if echo_to_print:
            print(info)

    def _update_hearing_me(self):
        self.hm_text.delete('1.end', tk.END)
        self.hm_text.insert(tk.END, "\n")
        hmc = self.hearing_me.compress_report(self.hearing_me.calls_hearing_my_call(self.band_tuple))
        hmg = self.hearing_me.compress_report(self.hearing_me.calls_hearing_my_grid(self.band_tuple))
        hmg_notc = [e for e in hmg if not e in hmc]
        self.hm_text.insert(tk.END, f"{' '.join(hmc)}\n", 'me')
        self.hm_text.insert(tk.END, f"{' '.join(hmg_notc)}\n")
      
    def _handle_udp_message(self, msg_dict):
        if msg_dict['mtype'] == 'STATUS':
            self.component_status[msg_dict['from']] = msg_dict['value']
        if msg_dict['mtype'] == 'info':
            print(msg_dict['info'])
        if msg_dict['mtype'] == 'decode':
            self._display_decode(msg_dict)
            msg_tuple = msg_dict['msg_tuple']
            if msg_tuple[0] == self.qso_dict['call'] and msg_tuple[1] == self.qso_dict['their_call']:
                self._progress_qso(msg_tuple)
        elif msg_dict['mtype'] == 'waterfall':
            self.waterfall_new_vals = [int(v) for v in msg_dict['data'].split(',')]

    def _display_decode(self, msg_dict):
        self.last_rx_time = time.time()
        new_cycle = msg_dict['cyclestart_string'] != self.qso_dict['cyclestart_string']
        new_cycle &= msg_dict['msg_tuple'][1] != self.qso_dict['call']
        if new_cycle:
            self.decodes_text.delete(1.0, tk.END)
            self.qso_dict.update({'cyclestart_string': msg_dict['cyclestart_string']})
            self._set_footer('')
        if time.time() - self.band_changed > 10:
            if msg_dict['msg_tuple'][1] != self.qso_dict['call']:
                self.pskr_upload.add_report(self.band_tuple, msg_dict)
            their_snr, dt, fHz, msg_tuple = msg_dict['their_snr'], msg_dict['dt'], msg_dict['fHz'], msg_dict['msg_tuple']
            wb = ''
            if self.adif_log:
                wb = self.adif_log.get_worked_before_info(msg_dict['msg_tuple'][1])
            hm = "@" if self.hearing_me.is_hearing_me(self.band_tuple, msg_tuple[1]) else ""
            display_text = self._format_display_text(their_snr, dt, f"{float(fHz):7.2f}", ' '.join(msg_tuple), wb, hm)
            idx = 1 * msg_tuple[0].startswith("CQ") + 2* msg_tuple[0].startswith(self.qso_dict['call']) + 3 * (msg_tuple[1] == self.qso_dict['call'])
            display_type = ['norm','cq','to_me','from_me', 'from_me'][idx]
            if self.highlight_call and self.highlight_call in display_text:
                disp1 = display_text.split(self.highlight_call)
                self.decodes_text.insert(tk.END, f"{disp1[0]}", display_type)
                self.decodes_text.insert(tk.END, f"{self.highlight_call}", 'highlight')
                self.decodes_text.insert(tk.END, f"{disp1[1]}\n", display_type)
            else:
                self.decodes_text.insert(tk.END, f"{display_text}\n", display_type)
            self.decodes_text.see('end')

    def _reset_qso_dict(self):
        self.qso_dict = {'cyclestart_string': '', 'fHz':'0', 'dt':'0', 'decode_info':'', 'msg_tuple':('','',''),
                 'call':self.config['station']['call'], 'grid':self.config['station']['grid'], 'my_snr':'-30',  
                 'their_call':'', 'their_grid':'', 'their_snr':'-30'}
        self.highlight_call = None

    def _row_click(self, e):
        curr = e.widget.index("current").split('.')[0]
        row_txt = e.widget.get(f"{curr}.0", f"{curr}.end")
        msg_str = row_txt.split('|')[1]
        msg_tuple = msg_str.split()
        if len(msg_tuple) == 2:
            msg_tuple = (msg_tuple[0], msg_tuple[1], '')
        if len(msg_tuple) == 4:
            msg_tuple = (f"{msg_tuple[0]} {msg_tuple[1]}", msg_tuple[2], msg_tuple[3])
        their_snr = row_txt.split()[0]
        self.qso_dict.update({'their_call':msg_tuple[1], 'their_snr': their_snr})
        self.highlight_call = msg_tuple[1]
        self._progress_qso(msg_tuple)
                    
    def _progress_qso(self, msg_tuple):
        hail, _, grid_rpt = msg_tuple
        reply = ''
        tcmc = f"{self.qso_dict['their_call']} {self.qso_dict['call']}"
        if hail.startswith("CQ"):
            reply = f"{tcmc} {self.qso_dict['grid'][:4]}"
        if hail.startswith(self.qso_dict['call']):
            reply = f"{tcmc} {self.qso_dict['their_snr']}"
            if any([m for m in ['+','-'] if m in grid_rpt]):
                reply = f"{tcmc} R{self.qso_dict['their_snr']}"
            if any([m for m in ['R+','R-','RRR'] if m in grid_rpt]):
                reply = f"{tcmc} RR73"
            if grid_rpt == 'RR73':
                reply = f"{tcmc} 73"
            if any([m for m in ['+','-'] if m in grid_rpt]): # grid_rpt == rpt
                self.qso_dict['my_snr'] = grid_rpt
            if not any([m for m in ['+','-','RR','73'] if m in grid_rpt]): # grid_rpt == grid
                self.qso_dict['their_grid'] = grid_rpt
        if reply:
            self._queue_transmit(reply)                
        if "73" in reply or "73" in grid_rpt:
            self.adif_log.log(self.band_tuple, self.qso_dict)
            self._set_footer(f"Logged QSO with {self.qso_dict['their_call']}")
            self.tx_cycle = None
            self.last_tx_message = ''
            self._reset_qso_dict()

    def _set_waterfall_info(self, e):
        w = self.waterfall_canvas.winfo_width()
        fHz = int(0.5 + e.x * 3000 / w)
        self.waterfall_canvas.itemconfigure(self.waterfall_info_txt, text = f"{fHz:.0f} Hz")

    def _waterfall_click(self, e):
        w = self.waterfall_canvas.winfo_width()
        fHz = int(0.5 + e.x * 3000 / w)
        self._set_tx_freq(fHz)

    def _set_tx_freq(self, tx_freq):
        self.tx_freq = tx_freq
        self.udp_comms_txr.udp_send_dict({'mtype':'set_tx_Hz', 'value':f"{self.tx_freq:.0f}"})  

    def _do_each_second(self):
        self.clock_lbl.config(text = time.strftime('%H:%M:%S'))
        self._update_hearing_me()
        if self.band_tuple:
            f_str = f"{self.band_tuple[1]:,.0f}"
            self.band_lbl.config(text = f"{self.band_tuple[0]} {f_str}")
        tnow = time.time()
        if tnow > self.last_rx_time + 2 * T_CYC:
            self.decodes_text.delete(1.0, tk.END)
        if self.running:
            self.clock_lbl.after(1000, self._do_each_second)
        
    def _update_pskr_uploader(self):
        if self.pskr_upload:
            self.pskr_upload.send_reports()
            if self.running:
                self.root.after(60000, self._update_pskr_uploader)

    def _send_waterfall_row(self):
        if self.waterfall_vals is None:
            self.waterfall_vals = self.waterfall_new_vals
        if self.waterfall_vals is not None:
            n = len(self.waterfall_vals)
            v, nv = self.waterfall_vals, self.waterfall_new_vals
            self.waterfall_vals = [max(0.8*v[i], nv[i]) for i in range(n)]
            w = self.waterfall_canvas.winfo_width()
            xys = [(i*w/n, 100-v) for i,v in enumerate(self.waterfall_vals)]
            self.waterfall_canvas.coords(self.waterfall_line, xys)
            x1, x2 = int(w * self.tx_freq/3000), int(w * (self.tx_freq + 8 * 6.25)/3000)
            xys = [x1, 100, x1, 0, x2, 0, x2, 100]
            self.waterfall_canvas.coords(self.waterfall_tx_freq, xys)
        if self.running:
            self.waterfall_canvas.after(250, self._send_waterfall_row)

    def _call_cq(self):
        self.tx_cycle = None
        self._queue_transmit(f"CQ {self.config['station']['call']} {self.config['station']['grid']}")

    def _queue_transmit(self, message = None):
        def generate_tx_audio(tx_message):
            self.udp_comms_txr.udp_send_dict({'mtype':'generate_tx_audio', 'message':tx_message})
        def start_tx_audio():
            self.udp_comms_txr.udp_send_dict({'mtype':'send_tx_audio'})
        if not message:
            message = self.last_tx_message
        if message:
            t_gen = time.time()
            generate_tx_audio(message)
            ct = (t_gen - TX_T0) % T_CYC
            if ct < MAX_CYCLETIME_TX_START or ct > 12 or message.startswith("CQ"):
                delay = 0 if 0 < ct < MAX_CYCLETIME_TX_START else T_CYC - ct
                self.last_tx_message = message
                cycle = int((t_gen + delay + 1) % (2 * T_CYC) / T_CYC)
                if self.tx_cycle is None:
                    self.tx_cycle = cycle
                else:
                    delay += (T_CYC if cycle != self.tx_cycle else 0)
                self._set_footer(f"Transmit message = {message} ({['even','odd'][self.tx_cycle]})")
                self.pending_start_tx_stream = self.root.after(int(delay * 1000), start_tx_audio)
                self.pending_ptt_on = self.root.after(int(delay * 1000), lambda: self._command_rig("T 1"))
                self.root.after(int(delay * 1000 + 13000), lambda: self._command_rig("T 0"))


    def _stop_transmit(self):
        self.udp_comms_txr.udp_send_dict({'mtype':'stop_tx_audio'})      
        self._command_rig("T 0")
        self.tx_cycle = None
        if self.pending_ptt_on:
            try:
                self.root.after_cancel(self.pending_ptt_on)
            except:
                pass
        if self.pending_start_tx_stream:
            try:
                self.root.after_cancel(self.pending_start_tx_stream)
            except:
                pass
            self._set_footer("Transmit cancelled")

#-----------------------------------------------------------------------------------------------------

def get_config(config_folder):
    config = configparser.ConfigParser()
    ini_file = f"{config_folder}/pyft8.ini"
    if not os.path.exists(ini_file):
        resp = input(f"No config file found at {ini_file}\nWould you like to create one (Y/N)? ")
        if resp.upper() !="Y":
            print("Exiting program")
            sys.exit()
        station_callsign = input(f"Please enter your callsign: ")
        station_grid = ''
        while len(station_grid) < 4:
            station_grid = input(f"Please enter your Maidenhead locator (at least 4 characters): ")
        config['station'] = {'call':station_callsign, 'grid':station_grid}
        config['bands'] = {'20m':14.074}
        config['rig_control'] = {'rigctl':'C:/Program Files/hamlib-w64-4.7.2/bin/rigctl.exe', 'port': 'COM4', 'baud_rate':9600, 'model':3070}
        config['soundcard'] = {'transmit':'Speak, CODEC', 'receive':'Mic, CODEC'}
        config['pskreporter'] = {'upload':'Y'}
        config['logging'] = {'logfile': f"{config_folder}/pyft8.adi"}
        with open(ini_file, 'w') as f:
            config.write(f)
        print(f"Wrote default config to {ini_file}. Please open and edit to add bands, frequencies and preferences and re-launch pyft8.")
        sys.exit()
    #print(f"Reading config from {ini_file}")
    config.read(ini_file)
    band_tuples = []
    if config.has_section('bands'):
        for band in config['bands']:
            fHz = int(1000000 * float(config['bands'][band]))
            band_tuples.append((band, fHz))
    return config, band_tuples

def run():
    config_folder = os.path.expanduser("~").replace('\\', '/')
    config, band_tuples = get_config(config_folder)
    gui = Gui(Receiver = Receiver, Transmitter = Transmitter, config_folder = config_folder,
              config = config, band_tuples = band_tuples)

if __name__ == "__main__":
    run()
