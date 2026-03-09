import numpy as np
import matplotlib.pyplot as plt
import time, queue
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button

rcParams['toolbar'] = 'None'
# ================== WATERFALL ======================================================

class Msg_box:
    def __init__(self, fig, ax, tbin, fbin, w, h, text, colors, attached_params, onclick, expire = 0):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.origin = (tbin, fbin)
        rect = Rectangle(self.origin, width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(tbin, fbin+2, text, fontsize='small', fontweight='bold' )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.set_properties(tbin, text, colors, attached_params, expire)

    def set_properties(self, tbin, text, colors, attached_params, expire):
        self.patch.set_x(tbin)
        self.attached_params = attached_params
        self.text_inst.set_x(tbin)
        self.text_inst.set_text(text)
        self.text_inst.set_color(colors[1])
        self.expire = expire
        self.patch.set_facecolor(colors[0])
        self.patch.set_visible(True)
        self.text_inst.set_visible(True)

    def hide_if_expired(self):
        if time.time() > self.expire > 0:
            self.patch.set_visible(False)
            self.text_inst.set_visible(False)

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick(self.text_inst.get_text(), self.attached_params)

class Gui:
    def __init__(self, dBgrid, hps, bpt, config, on_msg_click, on_control_click):
        self.mStation = {'c':config['station']['call'], 'g':config['station']['grid']}
        self.on_msg_click = on_msg_click
        self.on_control_click = on_control_click
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.msg_boxes = {}
        self.decode_queue = queue.Queue()
        self.simple_message_art = None
        self.make_layout(config)

    def simple_message(self, text, color):
        if self.simple_message_art:
            self.simple_message_art.remove()
        self.simple_message_art = self.fig.text(0.2,0.985, text, color = color)
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def make_layout(self, config):
        self.fig, self.ax_wf = plt.subplots(figsize=(10,10), frameon = False)
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        #self.fig.suptitle("PyFT8 by G1OJS")
        self.plt = plt
        plt.tight_layout()
        self.image = self.ax_wf.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        wf_ylim = self.ax_wf.get_ylim()
        self.ax_wf.set_axis_off()
        
        self.buttons = []
        styles = {'ctrl':{'fc':'grey','c':'black'}, 'band':{'fc':'green','c':'white'}}
        control_buttons = [{'label':'CQ','style':'ctrl','data':None}, {'label':'Repeat last','style':'ctrl','data':None},
                           {'label':'Tx off','style':'ctrl','data':None}]
                           #{'label':'Averaging','style':'ctrl','data':None}]
        for band, freq in config['bands'].items():
            control_buttons.append({'label':band,'style':'band','data':freq})
            
        btn_axs = []
        for i, btn in enumerate(control_buttons):
            btn_axs.append(plt.axes([0.05, 0.9 - 0.022 * i, 0.1, 0.02]))
            style = styles[btn['style']]
            btn_widg = Button(btn_axs[-1], btn['label'], color=style['fc'], hovercolor='skyblue')
            btn_widg.data = btn['data']
            btn_widg.on_clicked(lambda event, btn_widg=btn_widg: self.on_control_click(btn_widg))
            self.buttons.append(btn_widg)
        self.ani = FuncAnimation(self.fig, self._animate, interval = 40, frames=(100000), blit=True)

    def post_decode(self, decode):
        self.decode_queue.put(decode)

    def _show_decode(self, queued_decode):
        h0_idx, f0_idx, msg, attached_params = queued_decode
        colors = ['blue', 'white']
        if msg.startswith("CQ"): colors = ['green', 'white']
        if self.mStation['c'] in msg: colors = ['yellow', 'black']
        if msg.startswith(self.mStation['c']): colors = ['red', 'white']
        if not f0_idx in self.msg_boxes:
            btn = Msg_box(self.fig, self.ax_wf, h0_idx, f0_idx, 79*self.hps, 8*self.bpt, msg, colors, attached_params, onclick = self.on_msg_click)
            self.msg_boxes[f0_idx] = btn
        self.msg_boxes[f0_idx].set_properties(h0_idx, msg, colors, attached_params, expire = time.time() + 28)
        
    def _tidy_msg_boxes(self):
        for fb in self.msg_boxes:
            self.msg_boxes[fb].hide_if_expired()

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            self._show_decode(self.decode_queue.get())
        if (frame % 10 == 0):
            self._tidy_msg_boxes()
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts]

                                    
