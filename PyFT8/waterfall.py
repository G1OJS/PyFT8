import numpy as np
import matplotlib.pyplot as plt
import time, queue

# ================== WATERFALL ======================================================
class FT8Box:
    def __init__(self, ax, tbin, fbin, width, height, text):
        from matplotlib.patches import Rectangle
        self.ax = ax
        self.fbin = fbin
        self.patch = ax.add_patch(Rectangle((tbin, fbin), width=width, height=height,
                                            facecolor='blue',alpha=0.6, edgecolor='lime', lw=2))
        self.text = ax.text(tbin, fbin+2,text, color='white', fontsize='small', fontweight='bold' )
        self.update(tbin, text)
        
    def update(self, tbin, text):
        self.patch.set_x(tbin)
        self.text.set_x(tbin)
        self.text.set_text(text)
        self.modified = time.time()
        self.patch.set_facecolor('green' if "CQ" in text else "blue")


class Waterfall:
    def __init__(self, dBgrid, hps, bpt, before_plt_show, on_msg_click):
        from matplotlib.animation import FuncAnimation
        self.dBgrid = dBgrid
        self.midline = dBgrid.shape[0]/2
        self.hps, self.bpt = hps, bpt
        self.on_msg_click = on_msg_click
        self.boxes, self.messages = [], {}
        self.decode_queue = queue.Queue()
        self.fig, self.ax = plt.subplots(figsize=(10,10))
        self.fig.suptitle("G1OJS MiniPyFT8 with LDPC in ~ 300 lines")
        plt.tight_layout()
        self.ax.set_axis_off()
        self.image = self.ax.imshow(self.dBgrid.T,vmax=120,vmin=90,origin='lower',interpolation='none')
        self.ani = FuncAnimation(self.fig,self._animate,interval=40,frames=(100000), blit=True)
        before_plt_show(self)
        cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        plt.show()

    def onclick(self, event):
        cycle = int(event.xdata/self.midline)
        for fb in range(int(event.ydata - 8 * self.bpt), int(event.ydata)):
            if (cycle, fb) in self.messages:
                self.on_msg_click(self.messages[(cycle, fb)])
                break

    def tidy(self):
        for b in self.boxes:
            if (time.time() - b.modified) > 25:
                b.patch.set_visible(False)
                b.text.set_visible(False)
        self.boxes = [b for b in self.boxes if b.patch.get_visible()]

    def post_decode(self, tbin, fbin, text):
        self.decode_queue.put((tbin, fbin, text))

    def _animate(self, frame):
        self.image.set_data(self.dBgrid.T)
        while not self.decode_queue.empty():
            tbin, fbin, text = self.decode_queue.get()
            self._show_decode(tbin, fbin, text)
        if (frame % 10 == 0):
            self.tidy()
        return [self.image, *self.ax.patches, *self.ax.texts]

    def _show_decode(self, tbin, fbin, text):
        self.messages[(int(tbin/self.midline), fbin)] = text
        for existing_box in self.boxes:
            if existing_box.fbin == fbin and abs(existing_box.patch.get_x() - tbin) < 100:
                existing_box.update(tbin, text)
                return
        self.boxes.append(FT8Box(self.ax, tbin, fbin, 79*self.hps, 8*self.bpt, text))
                
