import numpy as np
import matplotlib.pyplot as plt
import time, queue
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button

rcParams['toolbar'] = 'None'
MAIN_TEXT_COLOR = '#f0f9fa'
TEXT_BACKGROUND_COLOR = '#2a2b2b'
INFO_TEXT_COLOR = 'white'
BUTTONCOLOR = 'grey'
HOVERCOLOR = 'darkgreen'
ACTIVE_BUTTON_COLOR = 'cyan'
INACTIVE_BUTTON_COLOR = '#edeef0'
MAX_FONT_SIZE_MAIN = 10
L = {'pmargin':0.04, 'sidebar_width': 0.16, 'banner_height':0.1, 'vsep1':0.01, 'hsep1':0.02}

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
                            '', color = MAIN_TEXT_COLOR, fontsize = self.fontsize))
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
    def __init__(self, fig, ax, tbin, fbin, w, h, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick 
        rect = Rectangle((tbin, fbin), width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(tbin, fbin+2, '', fontsize='small', fontweight='bold' )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.expire = 0 

    def set_properties(self, message):
        self.message = message
        self.patch.set_x(message.h0_idx)
        self.text_inst.set_x(message.h0_idx)
        self.patch.set_visible(True)
        self.text_inst.set_visible(True)
        self.expire = message.expire

    def set_appearance(self, message):
        self.text_inst.set_text(message.gui_text)
        colors = ['blue', 'white']
        if message.is_cq: colors = ['green', 'white']
        if message.is_from_me: colors = ['yellow', 'white']
        if message.is_to_me: colors = ['red', 'white']
        self.text_inst.set_color(colors[1])
        self.patch.set_facecolor(colors[0])
        
    def hide_if_expired(self):
        if time.time() > self.expire > 0:
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
        self.label2 = self.info_axs.text(0.03, 0.5, '', color = INFO_TEXT_COLOR, verticalalignment = 'center')
        self.btn_widg = Button(self.btn_axs, btn_label, color = BUTTONCOLOR, hovercolor = HOVERCOLOR)
        self.label = self.btn_widg.label
        self.label.set_color(MAIN_TEXT_COLOR)
        self.clickargs = clickargs
        self.active = False
        self.btn_widg.on_clicked(lambda x: onclick(clickargs))

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self._update_appearance()

    def set_info_text(self, text):
        self.label2.set_text(text)

    def get_info_text(self):
        return self.label2

    def _update_appearance(self):
        color = ACTIVE_BUTTON_COLOR if self.active else INACTIVE_BUTTON_COLOR
        self.label.set_color(color)
        self.label2.set_color(color)

class Gui:
    def __init__(self, dBgrid, hps, bpt, config, on_gui_sidebars_refresh, on_msg_click, on_control_click):
        if config is not None:
            self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.on_msg_click = on_msg_click
        self.on_control_click = on_control_click
        self.on_gui_sidebars_refresh = on_gui_sidebars_refresh
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.msg_boxes = {}
        self.decode_queue = queue.Queue()
        self.make_layout(config)
        self.display_cycle = 0
        self.ani = FuncAnimation(self.fig, self._animate, interval = 40, frames=(100000), blit=True)

    def set_bandstats_title(self, txt):
        self.band_stats.ax.set_title(txt, fontsize = 10)

    def make_layout(self, config):
        # figure
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4)) 
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        wf_top = 1-L['pmargin']-L['banner_height']-L['vsep1']
        wf_left = L['pmargin']+L['sidebar_width']+L['hsep1']

        # waterfall
        self.ax_wf = self.fig.add_axes([wf_left, L['pmargin'], 1-wf_left-L['pmargin'], wf_top-L['pmargin']])
        self.image = self.ax_wf.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])

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
                        btn_label = "CQ", onclick = self.on_control_click, clickargs = {'action':'CQ'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Repeat last", onclick = self.on_control_click, clickargs = {'action':'RPT_LAST'})                            
        self.button_boxes.append(bb)
        bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 100,
                        btn_label = "Tx off", onclick = self.on_control_click, clickargs = {'action':'TX_OFF'})                            
        self.button_boxes.append(bb)            
        for band, freq in config['bands'].items():
            bb = ButtonBox(self.fig, [L['pmargin'], wf_top - (len(self.button_boxes)+1) * bh + bs, L['sidebar_width'], bh-bs], btn_pc = 30,
                            btn_label = band, onclick = self.on_control_click, clickargs = {'action':'SET_BAND','band':band,'freq':freq})
            self.button_boxes.append(bb)

        # hearing me list
        self.hm = Scrollbox(self.fig, [L['pmargin'], L['pmargin'], L['sidebar_width'], wf_top - (len(self.button_boxes)+2) * bh + bs - L['vsep1']],
                            nlines = 30, monospace = True, fontsize = 8)
        

    def refresh_sidebars(self):
        self.display_cycle = (self.display_cycle + 1) %2
        self.on_gui_sidebars_refresh(self, self.display_cycle)
        
    def add_message_box(self, message):
        self.decode_queue.put(message)

    def _display_message_box(self, message):
        h0_idx, f0_idx = message.h0_idx, message.f0_idx
        if not f0_idx in self.msg_boxes:
            self.msg_boxes[f0_idx] = Msg_box(self.fig, self.ax_wf, h0_idx, f0_idx, 79*self.hps, 8*self.bpt, onclick = self.on_msg_click)
        self.msg_boxes[f0_idx].set_properties(message)
        self.msg_boxes[f0_idx].set_appearance(message)
        
    def _tidy_msg_boxes(self):
        for fb in self.msg_boxes:
            self.msg_boxes[fb].hide_if_expired()
 
    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            self._display_message_box(self.decode_queue.get())
        if (frame % 10 == 0):
            self._tidy_msg_boxes()
        if (frame % 30 == 0):
            self.refresh_sidebars()
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts, *self.band_stats.lineartists, *self.console.lineartists, *self.hm.lineartists,
                *[bb.label for bb in self.button_boxes], *[bb.label2 for bb in self.button_boxes]]

                                    
