import numpy as np
import matplotlib.pyplot as plt
import time, queue

# ================== WATERFALL ======================================================
class Button:
    def __init__(self, fig, ax, tbin, fbin, width, height, text, colors, params, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.origin = (tbin, fbin)
        self.patch = ax.add_patch(Rectangle(self.origin, width=width, height=height,
                                            facecolor=colors[0], alpha=0.6, edgecolor='lime', lw=2))
        self.text_inst = ax.text(tbin, fbin+2,text, color=colors[1], fontsize='small', fontweight='bold' )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.patch.set_x(tbin)
        self.params = params
        self.text_inst.set_x(tbin)
        self.text_inst.set_text(text)
        self.text_inst.set_color(colors[1])
        self.modified = time.time()
        self.patch.set_facecolor(colors[0])

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick(self.text_inst.get_text(), self.origin, self.params)

class Gui:
    def __init__(self, dBgrid, hps, bpt, mStation, on_msg_click):
        from matplotlib.animation import FuncAnimation
        self.mStation = mStation
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.on_msg_click = on_msg_click
        self.buttons = []
        self.decode_queue = queue.Queue()
        self.fig, self.ax = plt.subplots(figsize=(10,10))
        self.fig.suptitle("PyFT8 by G1OJS")
        plt.tight_layout()
        self.plt = plt
        self.ax.set_axis_off()
        self.image = self.ax.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        self.ani = FuncAnimation(self.fig, self._animate,interval=160,frames=(100000), blit=True)
        #cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)

    def post_decode(self, tbin, fbin, text, snr):
        self.decode_queue.put((tbin, fbin, text, snr))

    def _show_decode(self, tbin, fbin, text, snr):
        colors = ['blue', 'white']
        if text.startswith("CQ"): colors = ['green', 'white']
        if self.mStation['c'] in text: colors = ['yellow', 'black']
        if text.startswith(self.mStation['c']): colors = ['red', 'white']
        self.buttons.append(Button(self.fig, self.ax, tbin, fbin, 79*self.hps, 8*self.bpt, text, colors, snr, onclick = self.on_msg_click))
        
    def _tidy_buttons(self):
        for b in self.buttons:
            if (time.time() - b.modified) > 25:
                b.patch.set_visible(False)
                b.text_inst.set_visible(False)
        self.buttons = [b for b in self.buttons if b.patch.get_visible()]

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            tbin, fbin, text, snr = self.decode_queue.get()
            self._show_decode(tbin, fbin, text, snr)
        if (frame % 10 == 0):
            self._tidy_buttons()
        return [self.image, *self.ax.patches, *self.ax.texts]


                
