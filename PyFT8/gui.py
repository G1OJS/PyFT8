import numpy as np
import matplotlib.pyplot as plt
import time, queue

# ================== WATERFALL ======================================================
class FT8Box:
    def __init__(self, ax, tbin, fbin, width, height, text, colors):
        from matplotlib.patches import Rectangle
        self.ax = ax
        self.fbin = fbin
        self.patch = ax.add_patch(Rectangle((tbin, fbin), width=width, height=height,
                                            facecolor=colors[0],alpha=0.6, edgecolor='lime', lw=2))
        self.text = ax.text(tbin, fbin+2,text, color=colors[1], fontsize='small', fontweight='bold' )
        self.update(tbin, text, colors)
        
    def update(self, tbin, text, colors):
        self.patch.set_x(tbin)
        self.text.set_x(tbin)
        self.text.set_text(text)
        self.text.set_color(colors[1])
        self.modified = time.time()
        self.patch.set_facecolor(colors[0])

class Gui:
    def __init__(self, dBgrid, hps, bpt, mStation, on_msg_click):
        from matplotlib.animation import FuncAnimation
        self.mStation = mStation
        self.dBgrid = dBgrid
        self.midline = dBgrid.shape[0]/2
        self.hps, self.bpt = hps, bpt
        self.on_msg_click = on_msg_click
        self.boxes, self.messages = [], {}
        self.decode_queue = queue.Queue()
        self.fig, self.ax = plt.subplots(figsize=(10,10))
        self.fig.suptitle("PyFT8 by G1OJS")
        plt.tight_layout()
        self.plt = plt
        self.ax.set_axis_off()
        self.image = self.ax.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        self.ani = FuncAnimation(self.fig,self._animate,interval=160,frames=(100000), blit=True)
        cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)

    def onclick(self, event):
        cycle = int(event.xdata/self.midline)
        for fb in range(int(event.ydata - 8 * self.bpt), int(event.ydata)):
            if (cycle, fb) in self.messages:
                self.on_msg_click(clicked_msg = self.messages[(cycle, fb)])
                break

    def tidy(self):
        for b in self.boxes:
            if (time.time() - b.modified) > 29:
                b.patch.set_visible(False)
                b.text.set_visible(False)
        self.boxes = [b for b in self.boxes if b.patch.get_visible()]

    def post_decode(self, tbin, fbin, text, snr):
        self.decode_queue.put((tbin, fbin, text, snr))

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            tbin, fbin, text, snr = self.decode_queue.get()
            self._show_decode(tbin, fbin, text, snr)
        if (frame % 10 == 0):
            self.tidy()
        return [self.image, *self.ax.patches, *self.ax.texts]

    def _show_decode(self, tbin, fbin, text, snr):
        cycle = int(tbin/self.midline)
        self.messages[(cycle, fbin)] = (tbin, fbin, text, snr)
        colors = ['blue', 'white']
        if 'CQ' in text: colors = ['green', 'white']
        if self.mStation['c'] in text: colors = ['yellow', 'black']
        if text.startswith(self.mStation['c']): colors = ['red', 'white']
        
        for existing_box in self.boxes:
            if existing_box.fbin == fbin and abs(existing_box.patch.get_x() - tbin) < 100:
                existing_box.update(tbin, text, colors)
                return
        self.boxes.append(FT8Box(self.ax, tbin, fbin, 79*self.hps, 8*self.bpt, text, colors))
                
