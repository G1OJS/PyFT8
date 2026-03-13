import numpy as np
import matplotlib.pyplot as plt
import time, queue
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button

rcParams['toolbar'] = 'None'
# ================== WATERFALL ======================================================

class Scrollbox:
    def __init__(self, fig, ax, nlines = 5):
        self.fig, self.ax = fig, ax
        bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        self.fontsize = 0.5 * bbox.height * fig.dpi / nlines
        self.nlines = nlines
        self.line_height = 0.9 / nlines
        self.lines = []
        self.lineartists = []
        for i in range(self.nlines):
            self.lineartists.append(self.ax.text(0.03,1 - self.line_height * (i+1),
                            '', color = 'white', fontsize = self.fontsize))
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_facecolor('black')

    def print(self, text, color = 'white'):
        self.lines = self.lines[-(self.nlines-1):]
        self.lines.append({'text':text, 'color':color})
        for i, line in enumerate(self.lines):
            self.lineartists[i].set_text(line['text'])
            self.lineartists[i].set_color(line['color'])

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
        if message.is_from_me: colors = ['yellow', 'black']
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

class Gui:
    def __init__(self, dBgrid, hps, bpt, config, on_msg_click, on_control_click):
        if config is not None:
            self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.on_msg_click = on_msg_click
        self.on_control_click = on_control_click
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.msg_boxes = {}
        self.decode_queue = queue.Queue()
        self.pmarg = 0.04
        self.make_layout(config)
        self.ani = FuncAnimation(self.fig, self._animate, interval = 40, frames=(100000), blit=True)

    def make_layout(self, config, wf_left = 0.15, wf_top = 0.87):
        self.plt = plt
        self.fig = plt.figure(figsize = (10,10), facecolor=(.18, .71, .71, 0.4)) 
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.ax_wf = self.fig.add_axes([self.pmarg + wf_left, self.pmarg, 1-2*self.pmarg-wf_left, wf_top-self.pmarg])
        self.image = self.ax_wf.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none', aspect = 'auto')
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])
        self.ax_console = self.fig.add_axes([self.pmarg + wf_left, wf_top, 1-2*self.pmarg - wf_left, 1-self.pmarg-wf_top])
        self.console = Scrollbox(self.fig, self.ax_console)

        if config is not None:
            styles = {'ctrl':{'fc':'grey','c':'black'}, 'band':{'fc':'green','c':'white'}}
            button_defs = [{'label':'CQ','style':'ctrl','data':None}, {'label':'Repeat last','style':'ctrl','data':None},
                               {'label':'Tx off','style':'ctrl','data':None}]
                               #{'label':'Averaging','style':'ctrl','data':None}]
            for band, freq in config['bands'].items():
                button_defs.append({'label':band,'style':'band','data':freq})
            self._make_buttons(button_defs, styles, wf_top, 0.02, 0.1, 0.002)

    def _make_buttons(self, buttons, styles, btns_top, btn_h, btn_w, sep_h):
        self.buttons = []
        for i, btn in enumerate(buttons):
            btn_axs = plt.axes([self.pmarg, btns_top - (i+1) * btn_h, btn_w, btn_h-sep_h])
            style = styles[btn['style']]
            btn_widg = Button(btn_axs, btn['label'], color=style['fc'], hovercolor='skyblue')
            btn_widg.data = btn['data']
            btn_widg.on_clicked(lambda event, btn_widg=btn_widg: self.on_control_click(btn_widg))
            self.buttons.append(btn_widg)
        
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
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts, *self.console.lineartists]

                                    
