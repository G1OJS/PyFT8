import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
import queue
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from PyFT8.time_utils import time_utils

MAX_MSG_BOXES = 50
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

def text_to_rgba(s, *, dpi, **kwargs):
    fig = Figure(facecolor="none")
    fig.text(0, 0, s, **kwargs)
    with BytesIO() as buf:
        fig.savefig(buf, dpi=dpi, format="png", bbox_inches="tight",
                    pad_inches=0)
        buf.seek(0)
        rgba = np.asarray(Image.open(buf))
    return rgba

MESSAGE_TYPES = {'generic':{'bg':'blue', 'fg':'white'}, 'CQ':{'bg':'green', 'fg':'white'},'from_me': {'bg':'yellow', 'fg':'white'}, 'to_me':{'bg':'red', 'fg':'white'}} 
class Msg_box:
    def __init__(self, fig, ax, w, h, onclick):
        self.onclick = onclick
        self.fig, self.ax = fig, ax
        self.w, self.h = w, h
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.visible = False
        self.text_img = None
        self.text_inst, self.patch = None, None
        self.artists = [self.text_inst, self.patch]

    def set_properties(self, x, y, message, text_to_img = False):
        from matplotlib.patches import Rectangle
        rect = Rectangle((x, y), width=self.w, height=self.h, alpha=1, edgecolor='lime', lw=1)
        self.patch = self.ax.add_patch(rect)
        self.text_inst = self.ax.text(x, y+1, '', fontsize='small', fontweight = 'bold' )
        self.text_inst.set_text(message['display_text'])
        message_type_params = MESSAGE_TYPES[message['message_type']]
        self.text_inst.set_color(message_type_params['fg'])
        self.patch.set_facecolor(message_type_params['bg'])
        if text_to_img:
            text_img = self.fig.canvas.copy_from_bbox(self.text_inst.get_tightbbox())
            self.artists = [self.fig.figimage(text_img, x, y)]
        else:
            self.artists = [self.text_inst, self.patch]
        self.message = message
        self.cycle = message['origin']['odd_even']
        self.visible = True

    def hide(self):
        for a in self.artists:
            a.set_visible(False)
        self.visible = False

    def _onclick(self, event):
        b, _ = self.text_img.contains(event)
        if(b):
            self.onclick({'action': 'MESSAGE_CLICK', 'message':self.message})
    
class Gui:
    def __init__(self, config, on_click, history, console_print, get_band_info, hearing_me_since_mins = 5):
        self.plt = plt
        self.plt.ion()
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4))
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.config, self.on_click, self.history = config, on_click, history
        self.console_print, self.get_band_info = console_print, get_band_info
        self.wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        self.wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']
        self.hearing_me_since_mins = hearing_me_since_mins
        self.sidebars_last_update = 0
        self.sidebars_page = 0
        self._make_axes()
        self.msg_box_queue = queue.Queue()
        self.msg_boxes = {}
        self.msg_box_serial = 0
        self.image = None
        self._make_buttons()
        self.message_box_artists = []
        self.sidebars_artists = [*[bb.label for bb in self.button_boxes], *[bb.label2 for bb in self.button_boxes],
                                 *self.band_stats.lineartists, *self.console.lineartists, *self.hm.lineartists]

    def plot_loop(self, wf_data):
        w, h = wf_data['sig_w'], wf_data['sig_h']
        self.plt.pause(0.1)
        tlast = 0
        while True:
            t = time_utils.time()
            print(t - tlast)
            tlast = t
            self.fig.canvas.flush_events()
            
            if self.image is None:
                self.image = self.ax_wf.imshow(wf_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
            self.image.set_data(wf_data['data'])
        
            while not self.msg_box_queue.empty():
                message = self.msg_box_queue.get()
                o = message['origin']
                x = int(o['t0'] / wf_data['dt'] + o['odd_even'] * wf_data['pixels_per_cycle'])
                y = int(o['f0'] / wf_data['df'])
                self.msg_box_serial = (self.msg_box_serial + 1) % MAX_MSG_BOXES
                if not self.msg_box_serial in self.msg_boxes:
                    mb = Msg_box(self.fig, self.ax_wf, w, h, onclick = self._on_click_local)
                    self.msg_boxes[self.msg_box_serial] = mb
                self.msg_boxes[self.msg_box_serial].set_properties(x, y, message)
                self.message_box_artists += mb.artists
    
    def _on_click_local(self, clickargs):
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

    def after_new_search(self, curr_cycle):
        #self._refresh_sidebars()
        to_hide = [mb for mb in self.msg_boxes.values() if mb.visible and mb.cycle == curr_cycle]
        for mb in to_hide:
            mb.hide()

    def set_message(self, message):
        self.msg_box_queue.put(message)




                    


        
