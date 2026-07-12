import numpy as np
import matplotlib.pyplot as plt
import threading
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
    def __init__(self, fig, ax, x,y,w,h, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.ax = ax
        self.y = y
        rect = Rectangle((x, y), width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(x, self.y + 2, '', fontsize='small', fontweight='bold', clip_on = True )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.expire_time = 0

    def set_x(self, x):
        self.patch.set_x(x)
        self.text_inst = self.ax.text(x, self.y + 2, '', fontsize='small', fontweight='bold', clip_on = True )
        
    def set_message(self, message):
        self.message = message
        self.message_type = message['message_type']
        self.patch.set_visible(True)
        self.expire_time = time_utils.time() + 29.25
        message_type_params = MESSAGE_TYPES[self.message_type]
        self.patch.set_facecolor(message_type_params['bg'])
        display_text = message['display_text']
        self.text_inst.set_text(display_text)
        self.text_inst.set_color(message_type_params['fg'])
        self.text_inst.set_visible(True)

        
    def hide(self):
        self.patch.set_visible(False)
        self.text_inst.set_visible(False)

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
        self.hearing_me_since_mins = hearing_me_since_mins
        self._make_axes()
        self.lock = threading.Lock()
        self._initialise_artists()
        self._make_buttons()
        self.sidebars_dirty = True
        self.sidebars_artists = [*[bb.label for bb in self.button_boxes], *[bb.label2 for bb in self.button_boxes],
                    *self.band_stats.lineartists, *self.console.lineartists, *self.hm.lineartists]
        threading.Thread(target = self._housekeep_msg_boxes, daemon = True).start()
        self.ani = FuncAnimation(self.fig, self._animate, interval = 40, frames=(100000), blit=True)

    def _on_click_local(self, clickargs):
        self.sidebars_dirty = True
        if clickargs['action'] == "MESSAGE_CLICK":
            self.console_print(f"[GUI] Clicked on message '{clickargs['message']['message_text']}'")
        self.on_click(clickargs)

    def _make_axes(self):
        self.ax_wf = self.fig.add_axes([self.wf_left, L['pmargin'], 1-self.wf_left-L['pmargin'], self.wf_top-L['pmargin']])
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])
        self.band_stats = Scrollbox(self.fig, [L['pmargin'], self.wf_top+L['vsep1'], L['sidebar_width'], L['banner_height']], nlines = 4, monospace = True)
        self.band_stats.ax.text(-0.2,0.75,'Tx')
        self.band_stats.ax.text(-0.2,0.25,'Rx')
        self.console = Scrollbox(self.fig, [self.wf_left, self.wf_top+L['vsep1'], 1-self.wf_left-L['pmargin'], L['banner_height']])

    def _initialise_artists(self):
        self.msg_boxes = {}
        self.sidebars_refresh_last = 0
        self.sidebars_page = 0
        self.msg_box_artists = []
        self.image = self.ax_wf.imshow(self.waterfall_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')

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

    def _animate(self, frame):
        abs_time = time_utils.time()

        self.image.set_data(self.waterfall_data['data'])

        self.msg_box_artists = []
        for mb in self.msg_boxes.values():
            if abs_time < mb.expire_time: 
                self.msg_box_artists.append(mb.patch)
                self.msg_box_artists.append(mb.text_inst)
            else:
                mb.hide()
        
        if (abs_time - self.sidebars_refresh_last > 3):
            self.sidebars_dirty = True
            
        if self.sidebars_dirty:
            self._refresh_sidebars()
            self.sidebars_refresh_last = abs_time
            self.sidebars_dirty = False
 
        return [self.image, *self.msg_box_artists, *self.sidebars_artists]     


    def set_bandstats_title(self, txt):
        self.band_stats.ax.set_title(txt, fontsize = 10)

    def add_message_box(self, candidate, myCall):
        wf, o = self.waterfall_data, candidate.origin
        x = int(o['t0'] / wf['dt'] + o['odd_even'] * wf['pixels_per_cycle'])
        y = int(o['f0'] / wf['df'])
        w, h = self.waterfall_data['sig_w'], self.waterfall_data['sig_h']
        with self.lock:
            if not y in self.msg_boxes: 
                self.msg_boxes[y] = Msg_box(self.fig, self.ax_wf, x,y,w,h, onclick = self._on_click_local)
            else:
                self.msg_boxes[y].set_x(x)
            mb = self.msg_boxes[y]
            mb.snr = candidate.snr
            mb.odd_even = o['odd_even']
            mb.msg_tuple = candidate.msg_tuple
            mb.updated = False

    def _housekeep_msg_boxes(self):
        while True:
            time_utils.sleep(0.1)
            abs_time = time_utils.time()
            self.msg_box_artists = []
            with self.lock:
                for mb in self.msg_boxes.values():
                    time_utils.sleep(0)
                    if mb.updated == False:
                        hearing_me, geo_text, wb_time, wb_text = '', '', 0, ''
                        if self.history:
                            geo_text = self.history.get_geo_text(mb.msg_tuple[1], mb.msg_tuple[2])
                            wb_time = self.history.log_cache.get(mb.msg_tuple[1],'') 
                            wb_text = f"wb: {time_utils.format_duration(time_utils.time() - float(wb_time))}" if wb_time else ''
                            current_band = self.get_band_info()['current_band']
                            hearing_me = '# ' if self.history.is_hearing_me(current_band, mb.msg_tuple[1]) else ' '
                        myCall = self.config['station']['call']
                        message_type_value = 0 + 1*(mb.msg_tuple[1] == myCall) + 2*(mb.msg_tuple[0] == myCall) + 3*(mb.msg_tuple[0].startswith('CQ'))
                        message_type = ['generic', 'from_me', 'to_me', 'CQ'][message_type_value]
                        message = {'message_type':message_type,
                                    'message_text': ' '.join(mb.msg_tuple),
                                    'new_qso_info': {'call':mb.msg_tuple[1], 'rst_sent': f"{mb.snr:+03d}", 'grid_rpt':mb.msg_tuple[2], 'my_tx_cycle': 1-mb.odd_even},
                                    'display_text': f"{' '.join(mb.msg_tuple)} {hearing_me}{wb_text} {geo_text}"}
                        mb.set_message(message)
                        mb.updated = True

 
