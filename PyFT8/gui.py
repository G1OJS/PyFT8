import numpy as np
import matplotlib.pyplot as plt
import time, queue
from matplotlib.animation import FuncAnimation

# ================== WATERFALL ======================================================
class Button:
    def __init__(self, fig, ax, tbin, fbin, width, height, text, colors, params, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.origin = (tbin, fbin)
        rect = Rectangle(self.origin, width=width, height=height, facecolor=colors[0], alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(tbin, fbin+2, text, color=colors[1], fontsize='small', fontweight='bold' )
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
    def __init__(self, dBgrid, hps, bpt, mStation, on_msg_click, on_control_click):
        self.mStation = mStation
        self.on_msg_click = on_msg_click
        self.on_control_click = on_control_click
        self.dBgrid = dBgrid
        self.hps, self.bpt = hps, bpt
        self.buttons = []
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

    def post_decode(self, tbin, fbin, text, snr):
        self.decode_queue.put((tbin, fbin, f"{text} ({snr:+03d}dB)", snr))

    def _show_decode(self, tbin, fbin, text, snr):
        colors = ['blue', 'white']
        if text.startswith("CQ"): colors = ['green', 'white']
        if self.mStation['c'] in text: colors = ['yellow', 'black']
        if text.startswith(self.mStation['c']): colors = ['red', 'white']
        self.buttons.append(Button(self.fig, self.ax_wf, tbin, fbin, 79*self.hps, 8*self.bpt, text, colors, snr, onclick = self.on_msg_click))
        
    def _tidy_buttons(self):
        for b in self.buttons:
            if (time.time() - b.modified) > 28:
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
        return [self.image, *self.ax_wf.patches, *self.ax_wf.texts]

#============= TEST CODE =========================================================================

def on_control_click(btn_text, btn_origin, btn_params):
    print(btn_text)

def on_click(txt, snr):
    print(txt, snr)

def on_decode(c):
    gui.post_decode(c.h0_idx, c.f0_idx, c.msg, c.snr)
    print(f"{c.cyclestart_str} {c.snr} {c.dt:4.1f} {c.fHz} ~ {c.msg}")

if __name__ == "__main__":
    from PyFT8.receiver import Receiver, AudioIn
    audio_in = AudioIn(3100)
    input_device_idx = audio_in.find_device(['Mic', 'CODEC'])
    gui = Gui(audio_in.dBgrid_main, 4, 2,{'c':'', 'g':''}, on_click, on_control_click)
    rx = Receiver(audio_in, [200, 3100], on_decode)
    audio_in.start_streamed_audio(input_device_idx)
    print("Start rx")
    gui.plt.show()
                                        
