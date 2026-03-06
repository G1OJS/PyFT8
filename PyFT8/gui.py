import numpy as np
import matplotlib.pyplot as plt
import time, queue
from matplotlib.animation import FuncAnimation

# ================== WATERFALL ======================================================


class Button:
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
            self.onclick(self.text_inst.get_text(), self.origin, self.attached_params)

class Gui:
    def __init__(self, dBgrid, hps, bpt, mStation, on_msg_click, on_control_click):
        self.mStation = mStation
        self.on_msg_click = on_msg_click
        self.on_control_click = on_control_click
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.decode_buttons = {}
        self.decode_queue = queue.Queue()
        self.make_layout()

    def make_layout(self):
        self.fig, axs = plt.subplots(1, 2, figsize=(10,10), gridspec_kw={'width_ratios': [1, 6]})
        self.ax_controls, self.ax_wf = axs
        self.fig.suptitle("PyFT8 by G1OJS")
        self.plt = plt
        plt.tight_layout()
        self.image = self.ax_wf.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        wf_ylim = self.ax_wf.get_ylim()
        self.ax_controls.set_ylim(wf_ylim)
        self.ax_controls.set_axis_off()
        self.ax_wf.set_axis_off()
        self.buttons = []
        control_buttons = [('CQ','green','white'), ('Tx off','grey','white')]
        for i, btn in enumerate(control_buttons):
            btn = Button(self.fig, self.ax_controls, 0, wf_ylim[1] - (i+1)*16, 1, 16, btn[0], [btn[1], btn[2]], None, self.on_control_click)
            self.buttons.append(btn)
        band_buttons = [('160m','green','white', 1.840),('80m','green','white', 3.573),('60m','green','white', 5.357), ('40m','green','white', 7.074),
                        ('20m','green','white', 14.074),('15m','green','white', 21.074),('10m','green','white', 28.074), ('6m','green','white', 50.313),
                        ('2m','green','white', 144.174)]
        for i, btn in enumerate(band_buttons):
            btn = Button(self.fig, self.ax_controls, 0, wf_ylim[1] - (i+3)*16, 1, 16, btn[0], [btn[1], btn[2]], btn[3], self.on_control_click)
            self.buttons.append(btn)
        self.ani = FuncAnimation(self.fig, self._animate, interval = 40, frames=(100000), blit=True)

    def post_decode(self, decode):
        self.decode_queue.put(decode)

    def _show_decode(self, queued_decode):
        h0_idx, f0_idx, msg, attached_params = queued_decode
        colors = ['blue', 'white']
        if msg.startswith("CQ"): colors = ['green', 'white']
        if self.mStation['c'] in msg: colors = ['yellow', 'black']
        if msg.startswith(self.mStation['c']): colors = ['red', 'white']
        if not f0_idx in self.decode_buttons:
            btn = Button(self.fig, self.ax_wf, h0_idx, f0_idx, 79*self.hps, 8*self.bpt, msg, colors, attached_params, onclick = self.on_msg_click)
            self.decode_buttons[f0_idx] = btn
        self.decode_buttons[f0_idx].set_properties(h0_idx, msg, colors, attached_params, expire = time.time() + 28)
        
    def _tidy_decode_buttons(self):
        for fb in self.decode_buttons:
            self.decode_buttons[fb].hide_if_expired()

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            self._show_decode(self.decode_queue.get())
        if (frame % 10 == 0):
            self._tidy_decode_buttons()
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts]

                                    
