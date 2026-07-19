import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
import queue
from matplotlib.widgets import Button
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

def add_my_axes(fig, pos):
    ax = fig.add_axes(pos)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor(TEXT_BACKGROUND_COLOR)
    return ax

MESSAGE_TYPES = {'generic':{'bg':'blue', 'fg':'white', 'alpha':0.5}, 'CQ':{'bg':'green', 'fg':'white', 'alpha':0.8},
                 'from_me': {'bg':'yellow', 'fg':'black', 'alpha':0.95}, 'to_me':{'bg':'red', 'fg':'white', 'alpha':0.9}} 
class Msg_box:
    def __init__(self, fig, ax, x, y, w, h, message, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.fig, self.ax = fig, ax
        message_type_params = MESSAGE_TYPES[message['message_type']]
        rect = Rectangle((x, y), w, h, edgecolor='lime', lw=2)
        self.patch = self.ax.add_patch(rect)
        self.patch.set_visible(False)
        text_inst = self.ax.text(x, y+1, message['display_text'], fontsize='small', fontweight = 'bold' )
        text_inst.set_visible(False)
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        text_inst.set_color(message_type_params['fg'])
        self.patch.set_facecolor(message_type_params['bg'])
        self.patch.set_alpha(message_type_params['alpha'])
        self.message = message
        self.cycle = message['their_tx_cycle']
        self.artists = [self.patch, text_inst]
        for a in self.artists:
            a.set_visible(True)

    def draw(self):
        for a in self.artists:
            self.ax.draw_artist(a)

    def hide(self):
        for a in self.artists:
            a.set_visible(False)

    def remove(self):
        for a in self.artists:
            a.set_visible(False)
            a.remove()
            self.artists.remove(a)
        self = None

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick({'action': 'MESSAGE_CLICK', 'message':self.message})

class Panel:
    def __init__(self, fig, pos):
        self.fig = fig
        self.ax = self.fig.add_axes(pos)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_facecolor(TEXT_BACKGROUND_COLOR)
        box_h = self.ax.get_window_extent().height
        font_h = 10
        self.nlines = int(0.5*box_h / font_h)
        self.artists = []

    def clear(self):
        for a in self.artists:
            a.set_visible(False)
            a.remove()
        self.artists = [a for a in self.artists if a.get_visible()]

    def print_row(self, row_text, row_number, color = None):
        a = self.ax.text(0.03, 0.03+(self.nlines - row_number)/self.nlines, row_text)
        a.set_fontfamily('monospace')
        if color is not None:
            a.set_color(color)
        self.artists.append(a)
        self.ax.draw_artist(a)

class ButtonBox:
    def __init__(self, fig, box, btn_pc = 30, onclick = None, clickargs=None, btn_text = ' ', info_text = ' '):
        self.clickargs = clickargs
        btnbox, infobox = box.copy(), box.copy()
        btnbox[2] = box[2] * btn_pc /100
        infobox[2] = box[2] * (100-btn_pc) /100
        infobox[0] = box[0] + box[2] * (btn_pc /100)
        self.btn_axs = add_my_axes(fig, btnbox)
        self.btn_axs.set_facecolor(BUTTONCOLOR)
        self.btn_widg = Button(self.btn_axs, btn_text, color = BUTTONCOLOR, hovercolor = HOVERCOLOR)
        self.btn_widg.on_clicked(lambda x: onclick(clickargs))
        self.info_axs = add_my_axes(fig, infobox)
        self.info_art = self.info_axs.text(0.03, 0.5, info_text, color = INFO_TEXT_COLOR, verticalalignment = 'center', clip_on = True)        
        self.state_is_active = None
        self.set_state(False)

    def set_state(self, is_active: bool):
        if is_active != self.state_is_active:
            self.state_is_active = is_active
            color = ACTIVE_BUTTON_COLOR if is_active else INACTIVE_BUTTON_COLOR
            self.btn_widg.label.set_color(color)
            self.set_info_text(info_text = None, color = color)

    def set_info_text(self, info_text, color = None):
        if info_text is not None:
            self.info_art.set_text(info_text)
        if color is not None:
            self.info_art.set_color(color)
        
class Gui:
    def __init__(self, message_broker, rig_control, console_print, configured_bands, hearing_me_since_mins = 5):
        self.hearing_me_since_mins = hearing_me_since_mins
        self.waterfall_data = message_broker.waterfall_data
        self.history = message_broker.history
        self.qso_manager = None
        self.configured_bands = configured_bands
        self.console_print = console_print
        self.myCall, self.myGrid = message_broker.myCall, message_broker.myGrid
        self.band_info = {'current_band': None, 'fMHz':0, 'time_set':0}
        
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4))
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        self.wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']
        self.needs_redraw = False

        self.ax_wf = add_my_axes(self.fig, [self.wf_left, L['pmargin'], 1-self.wf_left-L['pmargin'], self.wf_top-L['pmargin']])
        self.image = self.ax_wf.imshow(self.waterfall_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')

        self.home_panel = Panel(self.fig, [L['pmargin'], self.wf_top+L['vsep1'], L['sidebar_width'], L['banner_height']])
        ax = self.home_panel.ax
        ax.draw_artist(ax.text(-0.15,0.75,'Tx'))
        ax.draw_artist(ax.text(-0.15,0.125,'Rx'))
       
        self.hearing_page = 0
        self.msg_boxes = []
        self.button_boxes = []

        bh, bs = 0.02, 0.002
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "CQ", onclick = self._on_click_local, clickargs = {'action':'CQ'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "Repeat last", onclick = self._on_click_local, clickargs = {'action':'RPT_LAST'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "Tx off", onclick = self._on_click_local, clickargs = {'action':'TX_OFF'})                            
        self.button_boxes.append(bb)            
        for band_info in self.configured_bands:
            band, fMHz = band_info['band'], band_info['fMHz']
            bb = ButtonBox(self.fig, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 30,
                            btn_text = band, onclick = self._on_click_local, clickargs = {'action':'SET_BAND', 'band':band, 'fMHz':fMHz})
            self.button_boxes.append(bb)
            
        hm_top = self.wf_top - (len(self.button_boxes)+2) * bh + bs - L['vsep1']

        self.console = Panel(self.fig, [self.wf_left, self.wf_top+L['vsep1'], 1-self.wf_left-L['pmargin'], L['banner_height']])
        self.console_rows_text = None
        self.hearing_panel = Panel(self.fig, [L['pmargin'], L['pmargin'], L['sidebar_width'], hm_top])

    def main_loop(self):
        last_ptr = 0
        self.plt.show(block = False)
        t0 = time_utils.time()
        while True:
            t = time_utils.time()
            #print(f"{t-t0:6.3f}")
            t0=t
            time_utils.sleep(0.05)
            self.image.set_data(self.waterfall_data['data'])
            if self.needs_redraw:
                self.needs_redraw = False
                plt.pause(0.01)
            else:
                self.ax_wf.draw_artist(self.image)
                for mb in self.msg_boxes:
                    mb.draw()
                self.fig.canvas.update()
                self.fig.canvas.flush_events()

    def before_search(self, curr_cycle):
        self._hide_msg_boxes(curr_cycle)
        
    def after_search(self,curr_cycle):
        self._refresh_hearing()
        self._refresh_band_buttons()
        self._refresh_home_panel()
        self._clear_msg_boxes(curr_cycle)

    def display_message(self, message):
        x = int(message['t0'] / self.waterfall_data['dt'] + message['their_tx_cycle'] * self.waterfall_data['pixels_per_cycle'])
        y = int(message['fHz'] / self.waterfall_data['df'])
        mb = Msg_box(self.fig, self.ax_wf, x, y, self.waterfall_data['sig_w'], self.waterfall_data['sig_h'], message, onclick = self._on_click_local)
        self.msg_boxes.append(mb)
        
    def get_band_info(self):
        return self.band_info

    def register_qso_manager(self, qsm):
        self.qso_manager = qsm

    def set_bandstats_title(self, txt):
        self.home_panel.ax.set_title(txt, fontsize = 10)
        
    def update_console(self, text, color):
        if self.console_rows_text is None:
            self.console_rows_text = [{'text':'','color':'white'} for i in range(self.console.nlines)]
        self.console_rows_text[1:] = self.console_rows_text[:-1]
        self.console_rows_text[0] = {'text':text,'color':color}
        self.console.clear()
        for row_number, row_text in enumerate(self.console_rows_text):
            self.console.print_row(row_text['text'], self.console.nlines - row_number,
                                   color = row_text['color'])
        self.needs_redraw = True

    def _on_click_local(self, clickargs):
        btn_action = clickargs['action']
        if(btn_action == 'SET_BAND'):
            current_band, freqMHz = clickargs['band'], clickargs['fMHz']
            self.band_info = {'current_band':current_band, 'fMHz':freqMHz, 'time_set':time_utils.time()}
            self.console_print(f"[PyFT8] Set band: {self.band_info['current_band']} {self.band_info['fMHz']}")
            self._refresh_hearing()
            for cyc in range(2):
                self._clear_msg_boxes(cyc)
            self._refresh_band_buttons()
            self._refresh_home_panel()
        if clickargs['action'] == "MESSAGE_CLICK":
            m = clickargs['message']
            m_string = f"{m['hail']} {m['their_call']} {m['grid_rpt']}"
            self.console_print(f"[GUI] Clicked on message '{m_string}'")
        self.needs_redraw = True
        self.qso_manager.on_click(clickargs)


    def _hide_msg_boxes(self, curr_cycle):
        to_hide = [mb for mb in self.msg_boxes if mb.cycle == curr_cycle]
        for mb in to_hide:
            mb.hide()
        self.needs_redraw = True

    def _clear_msg_boxes(self, curr_cycle):
        to_remove = [mb for mb in self.msg_boxes if mb.cycle == curr_cycle]
        self.msg_boxes = [mb for mb in self.msg_boxes if mb.cycle != curr_cycle]
        for mb in to_remove:
            mb.remove()
        self.needs_redraw = True

    def _text_row(self, ax, x, y, text = '', color = 'white', **args):
        art = ax.text(x, y, text, color = color)
        art.set_fontfamily('monospace')
        return art
   
    def _refresh_home_panel(self):
        current_band = self.band_info['current_band']
        if current_band is not None and self.history is not None:
            if current_band in self.history.home_most_remotes:
                tx_lead,  rx_lead = self.history.home_most_remotes[current_band]
                n_spotted, n_spotting = self.history.get_spot_counts(current_band, self.myCall)
                self.home_panel.clear()
                self.home_panel.print_row(f"{self.myCall:<7} {tx_lead[0]:<7}", 1, color = '#ff756b' )
                self.home_panel.print_row(f"{n_spotting:<7} {tx_lead[1]:<7}", 2, color = '#ff756b' )
                self.home_panel.print_row(f"{self.myCall:<7} {rx_lead[0]:<7}", 4, color = '#b6f0c6' )
                self.home_panel.print_row(f"{n_spotted:<7} {rx_lead[1]:<7}", 5, color = '#b6f0c6' )

    def _refresh_band_buttons(self):
        current_band = self.band_info['current_band']
        grd = self.myGrid[:4]
        for bb in self.button_boxes:
            button_band = bb.clickargs.get('band',None)
            if button_band is not None:
                bb.set_state(button_band == current_band)
                if button_band in self.history.home_activity:
                    cnts = self.history.home_activity[button_band]
                    bb.set_info_text(f"{cnts[0]}Tx, {cnts[1]}Rx")
        self.needs_redraw = True

    def _refresh_hearing(self):
        current_band = self.band_info['current_band']
        if current_band is not None and self.history is not None:
            historic_data = self.history.hearing_me.data if self.hearing_page  == 1 else self.history.heard_by_me.data
            new_calls_data = self.history.hearing_me_new if self.hearing_page  == 1 else self.history.heard_by_me_new
            timewindow_str = f"<{self.hearing_me_since_mins:.0f} mins"
            title_txt = f"Hearing me {timewindow_str}" if self.hearing_page==1 else f"Heard by me {timewindow_str}"
            self.hearing_panel.clear()
            self.hearing_panel.print_row(title_txt, 2, color = 'white')
            if current_band in historic_data:
                tnow = time_utils.time()
                band_rpts = historic_data[current_band]
                calls_now = [call for call in band_rpts if (tnow - band_rpts[call]['t']) < 60*self.hearing_me_since_mins]
                calls_now.sort(key = lambda c: band_rpts[c]['t'], reverse = True)
                subtitle_txt = f"{len(calls_now)}/{len(band_rpts)} now/ever"
                self.hearing_panel.print_row(subtitle_txt, 3, color = 'white')
                for i, remote_call in enumerate(calls_now[:self.hearing_panel.nlines - 3]):
                    rpt = band_rpts[remote_call]
                    row_txt = f"{remote_call:<7} {self.history.get_geo_text(remote_call)}"
                    color = 'white' if self.history.is_in_new_alert(current_band, remote_call, new_calls_data) else 'lime'
                    self.hearing_panel.print_row(row_txt, i+4, color = color)            
        self.hearing_page = (self.hearing_page +1 )%2






        
