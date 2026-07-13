import numpy as np
import matplotlib.pyplot as plt
import queue
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from PyFT8.time_utils import time_utils

rcParams['toolbar'] = 'None'
MAIN_TEXT_COLOR = '#f0f9fa'
TEXT_BACKGROUND_COLOR = '#2a2b2b'
INFO_TEXT_COLOR = 'white'
BUTTONCOLOR = 'grey'
HOVERCOLOR = 'darkgreen'
ACTIVE_BUTTON_COLOR = 'cyan'
INACTIVE_BUTTON_COLOR = '#edeef0'
MAX_FONT_SIZE_MAIN = 10
L = {'pmargin':0.04, 'sidebar_width': 0.17, 'banner_height':0.1, 'vsep1':0.01, 'hsep1':0.02}

# ================== WATERFALL ======================================================

class Scrollbox:
    def __init__(self, fig, box, nlines = 5, monospace = False, default_text = '', fontsize = None):
        self.fig = fig
        self.ax = fig.add_axes(box)
        self.default_text = default_text
        bbox = self.ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        self.fontsize = np.min([0.5 * bbox.height * fig.dpi / nlines, MAX_FONT_SIZE_MAIN]) if fontsize is None else fontsize
        self.nlines = nlines
        self.line_height = 0.9 / nlines
        self.lines = []
        self.lineartists = []
        for i in range(self.nlines):
            self.lineartists.append(self.ax.text(0.03,1 - self.line_height * (i+1),
                            '', color = MAIN_TEXT_COLOR, fontsize = self.fontsize, clip_on = True))
            if monospace:
                self.lineartists[-1].set_fontfamily('monospace')
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_facecolor(TEXT_BACKGROUND_COLOR)

    def scroll_print(self, text, color = MAIN_TEXT_COLOR):
        self.lines = self.lines[-(self.nlines-1):]
        self.lines.append({'text':text, 'color':color})
        for i, line in enumerate(self.lines):
            self.lineartists[i].set_text(line['text'])
            self.lineartists[i].set_color(line['color'])

    def clear(self):
        self.lines = []
        for i in range(self.nlines):
            self.lineartists[i].set_text(self.default_text)

    def list_print(self, lst, colors = None):
        for i, txt in enumerate(lst[:self.nlines]):
            if txt != self.lineartists[i].get_text():
                self.lineartists[i].set_text(txt)
                col = colors[i] if colors is not None and i < len(colors) else 'white'
                self.lineartists[i].set_color(col)
        for i in range(len(lst), self.nlines):
            if self.lineartists[i].get_text() != '':
                self.lineartists[i].set_text('')          

class ButtonBox:
    def __init__(self, fig, box, btn_pc = 30, onclick = None, clickargs=None, btn_label = ''):
        btnbox, infobox = box.copy(), box.copy()
        btnbox[2] = box[2] * btn_pc /100
        infobox[2] = box[2] * (100-btn_pc) /100
        infobox[0] = box[0] + box[2] * (btn_pc /100)
        self.btn_axs = fig.add_axes(btnbox)
        self.info_axs = fig.add_axes(infobox)
        self.info_axs.set_xticks([])
        self.info_axs.set_yticks([])
        self.info_axs.set_facecolor(TEXT_BACKGROUND_COLOR)
        self.label2 = self.info_axs.text(0.03, 0.5, '', color = INFO_TEXT_COLOR, verticalalignment = 'center', clip_on = True)
        self.btn_widg = Button(self.btn_axs, btn_label, color = BUTTONCOLOR, hovercolor = HOVERCOLOR)
        self.label = self.btn_widg.label
        self.label.set_color(MAIN_TEXT_COLOR)
        self.clickargs = clickargs
        self.active = False
        self.btn_widg.on_clicked(lambda x: onclick(clickargs))

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            color = ACTIVE_BUTTON_COLOR if self.active else INACTIVE_BUTTON_COLOR
            self.label.set_color(color)
            self.label2.set_color(color)

    def set_info_text(self, text):
        if text != self.label2:
            self.label2.set_text(text)

MESSAGE_TYPES = {'generic':{'bg':'blue', 'fg':'white'}, 'CQ':{'bg':'green', 'fg':'white'},'from_me': {'bg':'yellow', 'fg':'white'}, 'to_me':{'bg':'red', 'fg':'white'}} 
class Msg_box:
    def __init__(self, fig, ax, message, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.cycle = message['cycle']
        p = message['position']
        y, w, h = p['y'], p['sig_w'], p['sig_h']
        rect = Rectangle((0, y), width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(0, p['y'] + 1, '', fontsize='small', fontweight='bold', clip_on = True )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.expire_time = 0
        self.visible = True
        
    def set_properties(self, message):
        self.message, self.message_type = message, message['message_type']
        p, display_text = message['position'], message['display_text']
        x = p['x']
        self.patch.set_x(x)
        self.text_inst.set_x(x)
        self.patch.set_visible(True)
        self.text_inst.set_visible(True)
        self.visible = True
        self.expire_time = time_utils.time() + 29.25
        self.text_inst.set_text(display_text)
        
        message_type_params = MESSAGE_TYPES[self.message_type]
        self.text_inst.set_color(message_type_params['fg'])
        self.patch.set_facecolor(message_type_params['bg'])
        tdelay = (time_utils.cycle_time() - message['decode_completed']) %15
        print(f"{tdelay:5.2f}s after decode set props for {display_text} ")

    def update_text(self, display_text):
        self.text_inst.set_text(display_text)
        
    def hide(self):
        self.patch.set_visible(False)
        self.text_inst.set_visible(False)
        self.visible = False

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick({'action': 'MESSAGE_CLICK', 'message':self.message})
    
class Gui:
    def __init__(self, config, on_click, history, console_print, get_band_info, waterfall_data, hearing_me_since_mins = 5):
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4)) 
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.config, self.on_click, self.history, self.console_print, self.get_band_info, self.waterfall_data  = config, on_click, history, console_print, get_band_info, waterfall_data
        self.wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        self.wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']
        self.msg_box_display_queue = queue.Queue()
        self.msg_box_update_queue = queue.Queue()
        self.hearing_me_since_mins = hearing_me_since_mins
        self.sidebars_last_update = 0
        self.sidebars_page = 0
        self.sidebars_dirty = True
        self._make_axes()
        self.msg_boxes = {}
        self.image = self.ax_wf.imshow(self.waterfall_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
        self._make_buttons()
        self.display_queue_batch = []
        self.plt.pause(0.1)

    def _on_click_local(self, clickargs):
        self.sidebars_dirty = True
        if clickargs['action'] == "MESSAGE_CLICK":
            self.console_print(f"[GUI] Clicked on message '{clickargs['message']['msg_tuple']}'")
        self.on_click(clickargs)
        self._refresh_sidebars()

    def _make_axes(self):
        self.ax_wf = self.fig.add_axes([self.wf_left, L['pmargin'], 1-self.wf_left-L['pmargin'], self.wf_top-L['pmargin']])
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])
        self.band_stats = Scrollbox(self.fig, [L['pmargin'], self.wf_top+L['vsep1'], L['sidebar_width'], L['banner_height']], nlines = 4, monospace = True)
        self.band_stats.ax.text(-0.2,0.75,'Tx')
        self.band_stats.ax.text(-0.2,0.25,'Rx')
        self.console = Scrollbox(self.fig, [self.wf_left, self.wf_top+L['vsep1'], 1-self.wf_left-L['pmargin'], L['banner_height']])

    def _make_buttons(self):
        self.button_boxes = []
        bh, bs = 0.02, 0.002
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "CQ", onclick = self._on_click_local, clickargs = {'action':'CQ'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Repeat last", onclick = self._on_click_local, clickargs = {'action':'RPT_LAST'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Tx off", onclick = self._on_click_local, clickargs = {'action':'TX_OFF'})                            
        self.button_boxes.append(bb)            
        for band, freq in self.config['bands'].items():
            bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 30,
                            btn_label = band, onclick = self._on_click_local, clickargs = {'action':'SET_BAND', 'band':band, 'freq':freq})
            self.button_boxes.append(bb)

        self.hm = Scrollbox(self.fig, [L['pmargin'], L['pmargin'], L['sidebar_width'], self.wf_top - (len(self.button_boxes)+2) * bh + bs - L['vsep1']],
                            nlines = 30, monospace = True, fontsize = 8)

    def _refresh_sidebars(self):
        current_band = self.get_band_info()['current_band']

        # band stats
        grd = self.config['station']['grid'][:4]
        for bb in self.button_boxes:
            button_band = bb.clickargs.get('band','')
            if button_band:
                if current_band is not None:
                    bb.set_active(button_band == current_band)
                if button_band in self.history.home_activity:
                    cnts = self.history.home_activity[button_band]
                    bb.set_info_text(f"{cnts[0]}Tx, {cnts[1]}Rx")

        if current_band is not None and self.history is not None:
            # home square counts
            if current_band in self.history.home_most_remotes:
                tx_lead,  rx_lead = self.history.home_most_remotes[current_band]
                myCall = self.config['station']['call']
                n_spotted, n_spotting = self.history.get_spot_counts(current_band, myCall)
                self.band_stats.scroll_print(f"{myCall:<7} {tx_lead[0]:<7}", color = '#ff756b')
                self.band_stats.scroll_print(f"{n_spotting:<7} {tx_lead[1]:<7}", color = '#ff756b')
                self.band_stats.scroll_print(f"{myCall:<7} {rx_lead[0]:<7}", color = '#b6f0c6')
                self.band_stats.scroll_print(f"{n_spotted:<7} {rx_lead[1]:<7}", color = '#b6f0c6')

            #refresh hearing me / heard by me panel
            historic_data = self.history.hearing_me.data if self.sidebars_page  == 1 else self.history.heard_by_me.data
            new_calls_data = self.history.hearing_me_new if self.sidebars_page  == 1 else self.history.heard_by_me_new
            timewindow_str = f"<{self.hearing_me_since_mins:.0f} mins"
            title_txt = f"Hearing me {timewindow_str}" if self.sidebars_page==1 else f"Heard by me {timewindow_str}"
            display_rows = [(title_txt, 2e40, 'white')]
            tnow = time_utils.time()
            if current_band in historic_data:
                band_rpts = historic_data[current_band]
                calls_now = [call for call in band_rpts if (tnow - band_rpts[call]['t']) < 60*self.hearing_me_since_mins]
                subtitle_txt = f"{len(calls_now)}/{len(band_rpts)} now/ever"
                display_rows.append((subtitle_txt, 1e40, 'white'))
                for remote_call in calls_now:
                    rpt = band_rpts[remote_call]
                    snr, geo_text, timestamp = int(rpt['rp']), self.history.get_geo_text(remote_call, self.config['gui']['loc']), rpt['t']
                    color = 'white' if self.history.is_in_new_alert(current_band, remote_call, new_calls_data) else 'lime'
                    display_rows.append((f"{remote_call:<7} {snr:+03d} {geo_text:<12}", timestamp, color))
            display_rows.sort(key = lambda row: row[1], reverse = True)
            self.hm.list_print([row[0] for row in display_rows], [row[2] for row in display_rows])
        self.sidebars_page = (self.sidebars_page +1 )%2

    def set_bandstats_title(self, txt):
        self.band_stats.ax.set_title(txt, fontsize = 10)

    def enqueue_message_essentials(self, c):
        myCall = self.config['station']['call']
        message_type_value = 0 + 1*(c.msg_tuple[1] == myCall) + 2*(c.msg_tuple[0] == myCall) + 3*(c.msg_tuple[0].startswith('CQ'))
        message_type = ['generic', 'from_me', 'to_me', 'CQ'][message_type_value]
        wf, o = self.waterfall_data, c.origin
        x = int(o['t0'] / wf['dt'] + o['odd_even'] * wf['pixels_per_cycle'])
        y = int(o['f0'] / wf['df'])
        c.y = y
        message = { 'message_type':message_type, 'cycle':c.origin['odd_even'],
                    'position': {'x':x, 'y':y, 'sig_w':wf['sig_w'], 'sig_h':wf['sig_h']},
                    'msg_tuple':c.msg_tuple, 'decode_completed':c.decode_completed,
                    'new_qso_info': {'call':c.msg_tuple[1], 'rst_sent': f"{c.snr:+03d}", 'grid_rpt':c.msg_tuple[2], 'my_tx_cycle': 1-c.origin['odd_even']},
                    'display_text': f"{' '.join(c.msg_tuple)}"}
        
        self.msg_box_display_queue.put(message)

    def enqueue_message_updates(self, c):
        if self.history:
            current_band = self.get_band_info()['current_band']
            geo_text = self.history.get_geo_text(c.msg_tuple[1], c.msg_tuple[2])
            wb_time = self.history.log_cache.get(c.msg_tuple[1],'') 
            wb_text = f"wb: {time_utils.format_duration(time_utils.time() - float(wb_time))}" if wb_time else ''
            hearing_me = '# ' if self.history.is_hearing_me(current_band, c.msg_tuple[1]) else ' '
            display_text = f"{' '.join(c.msg_tuple)} {hearing_me}{wb_text} {geo_text}"
            self.msg_box_update_queue.put((c.y, display_text))

    def clear_message_boxes(self, curr_cycle):
        to_hide = [mb for mb in self.msg_boxes.values() if mb.visible and mb.cycle == curr_cycle]
        for mb in to_hide:
            mb.hide()
             
    def _plot_loop(self):
        while True:
            message = False
            
            while not self.msg_box_display_queue.empty():
                message = self.msg_box_display_queue.get()
                y = message['position']['y']
                if not y in self.msg_boxes:
                    self.msg_boxes[y] = Msg_box(self.fig, self.ax_wf, message, onclick = self._on_click_local)
                self.msg_boxes[y].set_properties(message)

            if not message:
                abs_time = time_utils.time()
                self.image.set_data(self.waterfall_data['data'])
                if abs_time %15 < 13 or self.sidebars_dirty:
                    if abs_time - self.sidebars_last_update > 3:
                        self._refresh_sidebars()
                        self.sidebars_last_update = abs_time
                        self.sidebars_dirty = False

                not_ready = []
                while not self.msg_box_update_queue.empty():
                    update = self.msg_box_update_queue.get()
                    y, display_text = update
                    if y in self.msg_boxes:
                        self.msg_boxes[y].update_text(display_text)
                    else:
                        not_ready.append(update)
                for update in not_ready:
                    self.msg_box_update_queue.put(update)
                    
            self.plt.pause(0.05)

        
