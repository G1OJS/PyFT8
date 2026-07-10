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

class Msg_box:
    def __init__(self, fig, ax, fbin, w, h, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick 
        rect = Rectangle((0, fbin), width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(0, fbin+2, '', fontsize='small', fontweight='bold', clip_on = True )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.expire = 0

    def set_properties(self, message, x):
        self.patch.set_x(x)
        self.text_inst.set_x(x)
        self.patch.set_visible(True)
        self.text_inst.set_visible(True)
        self.expire = time_utils.time() + 29.25
        self.text_inst.set_text(message['display_text'])
        colors = ['blue', 'white']
        if message['is_cq']: colors = ['green', 'white']
        if message['is_from_me']: colors = ['yellow', 'white']
        if message['is_to_me']: colors = ['red', 'white']
        self.text_inst.set_color(colors[1])
        self.patch.set_facecolor(colors[0])
        
    def hide_if_expired(self):
        if time_utils.time() > self.expire > 0:
            self.hide()

    def hide(self):
        self.patch.set_visible(False)
        self.text_inst.set_visible(False)

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick(self.message)

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


class Gui:
    def __init__(self, config, on_click):
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4)) 
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.config = config
        self.on_click = on_click
        self.rig = None
        self.wf_data = None
        self.band_info = {'current_band':None}
        self.sidebars_refresh_last = 0
        self.sidebars_page = 0
        self.msg_boxes = {}
        self.new_messages = queue.Queue()
        self.make_layout()

    def init_waterfall(self, wf_data):
        self.wf_data = wf_data
        self.image = self.ax_wf.imshow(self.wf_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])
        self.ani = FuncAnimation(self.fig, self._animate, interval = 25, frames=(100000), blit=True)

    def make_layout(self):
        # waterfall axis
        wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']
        self.ax_wf = self.fig.add_axes([wf_left, L['pmargin'], 1-wf_left-L['pmargin'], wf_top-L['pmargin']])

        # band stats
        self.band_stats = Scrollbox(self.fig, [L['pmargin'], wf_top+L['vsep1'], L['sidebar_width'], L['banner_height']], nlines = 4, monospace = True)
        self.band_stats.ax.text(-0.2,0.75,'Tx')
        self.band_stats.ax.text(-0.2,0.25,'Rx')

        # console
        self.console = Scrollbox(self.fig, [wf_left, wf_top+L['vsep1'], 1-wf_left-L['pmargin'], L['banner_height']])

        # control buttons
        self.button_boxes = []
        bh, bs = 0.02, 0.002
        bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "CQ", onclick = self.on_click, clickargs = {'action':'CQ'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Repeat last", onclick = self.on_click, clickargs = {'action':'RPT_LAST'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Tx off", onclick = self.on_click, clickargs = {'action':'TX_OFF'})                            
        self.button_boxes.append(bb)            
        for band, freq in self.config['bands'].items():
            bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 30,
                            btn_label = band, onclick = self.on_click, clickargs = {'action':'SET_BAND','band':band,'freq':freq})
            self.button_boxes.append(bb)

        # hearing me list
        self.hm = Scrollbox(self.fig, [L['pmargin'], L['pmargin'], L['sidebar_width'], wf_top - (len(self.button_boxes)+2) * bh + bs - L['vsep1']],
                            nlines = 30, monospace = True, fontsize = 8)

    def set_bandstats_title(self, txt):
        self.band_stats.ax.set_title(txt, fontsize = 10)

    def refresh_sidebars(self):
        current_band = self.band_info['current_band']
        if current_band is not None and current_band in history is not None:
        
            # band stats
            grd = self.config['station']['grid'][:4]
            for bb in self.button_boxes:
                button_band = bb.clickargs.get('band','')
                if button_band:
                    bb.set_active(button_band == self.band_info['current_band'])
                    if button_band in history.home_activity:
                        cnts = history.home_activity[button_band]
                        bb.set_info_text(f"{cnts[0]}Tx, {cnts[1]}Rx")

            # home square counts
            if current_band in history.home_most_remotes:
                tx_lead,  rx_lead = history.home_most_remotes[current_band]
                call = config['station']['call']
                n_spotted, n_spotting = history.get_spot_counts(current_band, call)
                self.band_stats.scroll_print(f"{call:<7} {tx_lead[0]:<7}", color = '#ff756b')
                self.band_stats.scroll_print(f"{n_spotting:<7} {tx_lead[1]:<7}", color = '#ff756b')
                self.band_stats.scroll_print(f"{call:<7} {rx_lead[0]:<7}", color = '#b6f0c6')
                self.band_stats.scroll_print(f"{n_spotted:<7} {rx_lead[1]:<7}", color = '#b6f0c6')

            #refresh hearing me / heard by me panel
            historic_data = history.hearing_me.data if self.sidebars_page  == 1 else history.heard_by_me.data
            new_calls_data = history.hearing_me_new if self.sidebars_page  == 1 else history.heard_by_me_new
            timewindow_str = f"<{HEARING_PANEL_LIFE_MINS:.0f} mins"
            title_txt = f"Hearing me {timewindow_str}" if display_cycle==1 else f"Heard by me {timewindow_str}"
            display_rows = [(title_txt, 2e40, 'white')]
            tnow = time_utils.time()
            if current_band in historic_data:
                band_rpts = historic_data[current_band]
                calls_now = [call for call in band_rpts if (tnow - band_rpts[call]['t']) < 60*HEARING_PANEL_LIFE_MINS]
                subtitle_txt = f"{len(calls_now)}/{len(band_rpts)} now/ever"
                display_rows.append((subtitle_txt, 1e40, 'white'))
                for remote_call in calls_now:
                    rpt = band_rpts[remote_call]
                    snr, geo_text, timestamp = int(rpt['rp']), history.get_geo_text(remote_call, config['gui']['loc']), rpt['t']
                    color = 'white' if history.is_in_new_alert(b, remote_call, new_calls_data) else 'lime'
                    display_rows.append((f"{remote_call:<7} {snr:+03d} {geo_text:<12}", timestamp, color))
            display_rows.sort(key = lambda row: row[1], reverse = True)
            self.hm.list_print([row[0] for row in display_rows], [row[2] for row in display_rows])

        self.sidebars_refresh_last = time_utils.time()
        self.sidebars_page = (self.sidebars_page +1 )%2

    def add_message_box(self, message_info):
        self.new_messages.put(message_info)

    def hide_msg_boxes(self):
        for fb in self.msg_boxes:
            self.msg_boxes[fb].hide()
 
    def _animate(self, frame):
        self.image.set_data(self.wf_data['data'])
        
        for fb in self.msg_boxes:
            self.msg_boxes[fb].hide_if_expired()
            
        while not self.new_messages.empty():
            message = self.new_messages.get()
            wf = self.wf_data
            o = message['origin']
            x = o['t0'] / wf['dt'] + o['odd_even'] * wf['pixels_per_cycle']
            y = o['f0'] / wf['df']
            if not y in self.msg_boxes: 
                self.msg_boxes[y] = Msg_box(self.fig, self.ax_wf, y, self.wf_data['sig_w'], self.wf_data['sig_h'], onclick = self.on_click)
            self.msg_boxes[y].set_properties(message, x)
            
        if time_utils.time() - self.sidebars_refresh_last > 3:            
            self.refresh_sidebars()
            return [self.image, *self.ax_wf.patches, *self.ax_wf.texts, *self.band_stats.lineartists, *self.console.lineartists, *self.hm.lineartists,
                *[bb.label for bb in self.button_boxes], *[bb.label2 for bb in self.button_boxes]]
        
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts]
        

