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


class ButtonBox:
    def __init__(self, fig, _reset_axis, box, btn_pc = 30, onclick = None, clickargs=None, btn_text = ' ', info_text = ' '):
        self._reset_axis = _reset_axis
        self.clickargs = clickargs
        btnbox, infobox = box.copy(), box.copy()
        btnbox[2] = box[2] * btn_pc /100
        infobox[2] = box[2] * (100-btn_pc) /100
        infobox[0] = box[0] + box[2] * (btn_pc /100)
        self.btn_axs = fig.add_axes(btnbox)
        self.btn_widg = Button(self.btn_axs, btn_text, color = BUTTONCOLOR, hovercolor = HOVERCOLOR)
        self.btn_widg.on_clicked(lambda x: onclick(clickargs))
        self.info_axs = fig.add_axes(infobox)
        self.info_text_inst = self.info_axs.text(0.03, 0.5, info_text, color = INFO_TEXT_COLOR, verticalalignment = 'center', clip_on = True)        
        self.set_info_text(info_text)
        self.state_is_active = None
        self.set_state(False)

    def set_state(self, is_active: bool):
        if is_active != self.state_is_active:
            self.state_is_active = is_active
            color = ACTIVE_BUTTON_COLOR if is_active else INACTIVE_BUTTON_COLOR
            self.btn_widg.label.set_color(color)
            self.btn_axs.draw_artist(self.btn_widg.label)
            if self.info_text_inst: 
                self.info_text_inst.set_color(color)
                self.info_axs.draw_artist(self.info_text_inst)

    def set_info_text(self, info_text):
        self._reset_axis(self.info_axs)
        self.info_text_inst.set_text(info_text)
        self.info_axs.draw_artist(self.info_text_inst)


MESSAGE_TYPES = {'generic':{'bg':'blue', 'fg':'white', 'alpha':0.5}, 'CQ':{'bg':'green', 'fg':'white', 'alpha':0.8},
                 'from_me': {'bg':'yellow', 'fg':'black', 'alpha':0.95}, 'to_me':{'bg':'red', 'fg':'white', 'alpha':0.9}} 
class Msg_box:
    def __init__(self, fig, ax, w, h, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.fig, self.ax = fig, ax
        rect = Rectangle((0, 0), w, h, edgecolor='lime', lw=2)
        self.patch = self.ax.add_patch(rect)
        self.text_inst = self.ax.text(0, 0, '', fontsize='small', fontweight = 'bold' )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.active = False

    def set_properties(self, x, y, message):
        self.patch.set_xy((x, y))
        self.text_inst.set_position((x, y+1))
        self.text_inst.set_text(message['display_text'])
        message_type_params = MESSAGE_TYPES[message['message_type']]
        self.text_inst.set_color(message_type_params['fg'])
        self.patch.set_facecolor(message_type_params['bg'])
        self.patch.set_alpha(message_type_params['alpha'])
        self.message = message
        self.cycle = message['origin']['odd_even']
        self.active = True

    def _onclick(self, event):
        if self.active:
            b, _ = self.patch.contains(event)
            if(b):
                self.onclick({'action': 'MESSAGE_CLICK', 'message':self.message})
    
class Gui:
    def __init__(self, message_broker, rig_control, console_print, configured_bands, hearing_me_since_mins = 5):
        self.hearing_me_since_mins = hearing_me_since_mins
        self.waterfall_data = message_broker.waterfall_data
        self.history = message_broker.history
        self.configured_bands = configured_bands
        self.myCall, self.myGrid = message_broker.myCall, message_broker.myGrid
        self.band_info = {'current_band': None, 'fMHz':0, 'time_set':0}
        
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4))
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        self.wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']

        self.ax_wf = self.fig.add_axes([self.wf_left, L['pmargin'], 1-self.wf_left-L['pmargin'], self.wf_top-L['pmargin']])
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])

        self.image = self.ax_wf.imshow(self.waterfall_data['data'],vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
        self.ax_ss = self.fig.add_axes([L['pmargin'], self.wf_top+L['vsep1'], L['sidebar_width'], L['banner_height']])
        self.ax_cs = self.fig.add_axes([self.wf_left, self.wf_top+L['vsep1'], 1-self.wf_left-L['pmargin'], L['banner_height']])

        self.console_rows = [('','white'),('','white'),('','white'),('','white'),('','white')]
        self.hearing_page = 0
        self.active_msg_boxes = []
        self.inactive_msg_boxes = []
        self.button_boxes = []

        bh, bs = 0.02, 0.002
        bb = ButtonBox(self.fig, self._reset_axis, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "CQ", onclick = self._on_click_local, clickargs = {'action':'CQ'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, self._reset_axis, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "Repeat last", onclick = self._on_click_local, clickargs = {'action':'RPT_LAST'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, self._reset_axis, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_text = "Tx off", onclick = self._on_click_local, clickargs = {'action':'TX_OFF'})                            
        self.button_boxes.append(bb)            
        for band_info in self.configured_bands:
            band, fMHz = band_info['band'], band_info['fMHz']
            bb = ButtonBox(self.fig, self._reset_axis, [L['pmargin'], self.wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 30,
                            btn_text = band, onclick = self._on_click_local, clickargs = {'action':'SET_BAND', 'band':band, 'fMHz':fMHz})
            self.button_boxes.append(bb)
            
        hm_top = self.wf_top - (len(self.button_boxes)+2) * bh + bs - L['vsep1']
        self.ax_hm = self.fig.add_axes([L['pmargin'], L['pmargin'], L['sidebar_width'], hm_top])

        self.tlast = 0
        self.band_info = {'current_band': None, 'fMHz':0, 'time_set':0}
        self._refresh_hearing()
        self._refresh_band_buttons()
        self._refresh_square_stats()

    def get_band_info(self):
        return self.band_info

    def set_bandstats_title(self, txt):
        self.ax_ss.set_title(txt, fontsize = 10)
        
    def update_console(self, text, color, nlines = 5):
        ax = self.ax_cs
        bbox = ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
        rowheight = bbox.height * self.fig.dpi / nlines
        fontsize = np.min([0.5 * rowheight, MAX_FONT_SIZE_MAIN])
        self._reset_axis(ax)
        self.console_rows[1:] = self.console_rows[:-1]
        self.console_rows[0] = (text, color)
        for i, rw in enumerate(self.console_rows):
            ax.draw_artist(self._text_row(ax, 0.03, .03+0.9*i/len(self.console_rows), rw[0], color = rw[1], fontsize = fontsize))

    def monitor_waterfall(self):
        last_ptr = 0
        self.plt.show(block = False)
        while True:
            time_utils.sleep(0.01)
            ptr = self.waterfall_data['ptr']()
            if abs(ptr-last_ptr)>1:
                last_ptr = ptr

                self.image.set_data(self.waterfall_data['data'])
                self.ax_wf.draw_artist(self.image)
                for mb in self.active_msg_boxes:
                    self.ax_wf.draw_artist(mb.patch)
                    self.ax_wf.draw_artist(mb.text_inst)
                self.fig.canvas.update()
                self.fig.canvas.flush_events()

    def after_new_search(self, curr_cycle):
        self._refresh_hearing()
        self._clear_msg_boxes(curr_cycle)
        self._refresh_band_buttons()
        self._refresh_square_stats()

    def display_message(self, message):
        x = int(message['t0'] / self.waterfall_data['dt'] + message['their_tx_cycle'] * self.waterfall_data['pixels_per_cycle'])
        y = int(message['fHz'] / self.waterfall_data['df'])
        mb = self._get_msg_box()
        self.active_msg_boxes.append(mb)
        mb.set_properties(x, y, message)

    def _reset_axis(self, ax):
        from matplotlib.patches import Rectangle
        rect = Rectangle((0, 0), 1, 1, facecolor = TEXT_BACKGROUND_COLOR)
        ax.draw_artist(ax.add_patch(rect))
        ax.set_xticks([])
        ax.set_yticks([])

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
            self._refresh_square_stats()
        if clickargs['action'] == "MESSAGE_CLICK":
            self.console_print(f"[GUI] Clicked on message '{clickargs['message']['msg_tuple']}'")
        self.on_click(clickargs)

    def _clear_msg_boxes(self, curr_cycle):
        to_remove = [mb for mb in self.active_msg_boxes if mb.cycle == curr_cycle]
        for mb in to_remove:
            mb.active = False
            self.inactive_msg_boxes.append(mb)
            self.active_msg_boxes.remove(mb)

    def _get_msg_box(self):
        if len(self.inactive_msg_boxes) == 0:
            mb = Msg_box(self.fig, self.ax_wf, self.waterfall_data['sig_w'], self.waterfall_data['sig_h'], onclick = self._on_click_local)
        else:
            mb = self.inactive_msg_boxes.pop()
        return mb

    def _text_row(self, ax, x, y, text = '', color = 'white', **args):
        art = ax.text(x, y, text, color = color)
        art.set_fontfamily('monospace')
        return art
   
    def _refresh_square_stats(self):
        ax = self.ax_ss
        self._reset_axis(ax)
        ax.draw_artist(ax.text(-0.2,0.75,'Tx'))
        ax.draw_artist(ax.text(-0.2,0.25,'Rx'))
        current_band = self.band_info['current_band']
        if current_band is not None and self.history is not None:
            if current_band in self.history.home_most_remotes:
                tx_lead,  rx_lead = self.history.home_most_remotes[current_band]
                n_spotted, n_spotting = self.history.get_spot_counts(current_band, myCall)
                ax.draw_artist(self._text_row(ax, 0.03, .75, f"{myCall:<7} {tx_lead[0]:<7}", color = '#ff756b' ))
                ax.draw_artist(self._text_row(ax, 0.03, .6, f"{n_spotting:<7} {tx_lead[1]:<7}", color = '#ff756b' ))
                ax.draw_artist(self._text_row(ax, 0.03, .25, f"{myCall:<7} {rx_lead[0]:<7}", color = '#b6f0c6' ))
                ax.draw_artist(self._text_row(ax, 0.03, .1, f"{n_spotted:<7} {rx_lead[1]:<7}", color = '#b6f0c6' ))

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
        self.fig.canvas.update()
        self.fig.canvas.flush_events()

    def _refresh_hearing(self):
        current_band = self.band_info['current_band']
        ax = self.ax_hm
        self._reset_axis(ax)
        line_height = 0.03
        bbox = ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
        nlines = int(0.9 / line_height)
        row_artists = []
        if current_band is not None and self.history is not None:
            historic_data = self.history.hearing_me.data if self.hearing_page  == 1 else self.history.heard_by_me.data
            new_calls_data = self.history.hearing_me_new if self.hearing_page  == 1 else self.history.heard_by_me_new
            timewindow_str = f"<{self.hearing_me_since_mins:.0f} mins"
            title_txt = f"Hearing me {timewindow_str}" if self.hearing_page==1 else f"Heard by me {timewindow_str}"
            row_artists.append(self._text_row(ax, 0.03, 1 - line_height, title_txt, color = 'white'))
            if current_band in historic_data:
                tnow = time_utils.time()
                band_rpts = historic_data[current_band]
                calls_now = [call for call in band_rpts if (tnow - band_rpts[call]['t']) < 60*self.hearing_me_since_mins]
                calls_now.sort(key = lambda c: band_rpts[c]['t'], reverse = True)
                subtitle_txt = f"{len(calls_now)}/{len(band_rpts)} now/ever"
                row_artists.append(self._text_row(ax, 0.03, 1 - 2*line_height, subtitle_txt, color = 'white'))
                for i, remote_call in enumerate(calls_now[:nlines - 3]):
                    rpt = band_rpts[remote_call]
                    row_txt = f"{remote_call:<7} {self.history.get_geo_text(remote_call, self.config['gui']['loc'])}"
                    color = 'white' if self.history.is_in_new_alert(current_band, remote_call, new_calls_data) else 'lime'
                    row_artists.append(self._text_row(ax, 0.03, 1 - line_height*(i+3.2), row_txt, color = color))
        for row_art in row_artists:
            ax.draw_artist(row_art)
        self.fig.canvas.update()
        self.fig.canvas.flush_events()
        self.hearing_page = (self.hearing_page +1 )%2






        
