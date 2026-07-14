import numpy as np
import matplotlib.pyplot as plt
import queue
from matplotlib import rcParams
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from PyFT8.time_utils import time_utils

DO_METRICS = True

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
                            '', color = MAIN_TEXT_COLOR, fontsize = self.fontsize, clip_on = True))
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
        self.label2 = self.info_axs.text(0.03, 0.5, '', color = INFO_TEXT_COLOR, verticalalignment = 'center', clip_on = True)
        self.btn_widg = Button(self.btn_axs, btn_label, color = BUTTONCOLOR, hovercolor = HOVERCOLOR)
        self.label = self.btn_widg.label
        self.label.set_color(MAIN_TEXT_COLOR)
        self.clickargs = clickargs
        self.active = False
        self.btn_widg.on_clicked(lambda x: onclick(clickargs))

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            color = ACTIVE_BUTTON_COLOR if self.active else INACTIVE_BUTTON_COLOR
            self.label.set_color(color)
            self.label2.set_color(color)

    def set_info_text(self, text):
        if text != self.label2:
            self.label2.set_text(text)

MESSAGE_TYPES = {'generic':{'bg':'blue', 'fg':'white'}, 'CQ':{'bg':'green', 'fg':'white'},'from_me': {'bg':'yellow', 'fg':'white'}, 'to_me':{'bg':'red', 'fg':'white'}} 
class Msg_box:
    def __init__(self, fig, ax, x,y,w,h, message, onclick):
        from matplotlib.patches import Rectangle
        self.onclick = onclick
        self.cycle = message['cycle']
        rect = Rectangle((x, y), width=w, height=h, alpha=0.6, edgecolor='lime', lw=2)
        self.patch = ax.add_patch(rect)
        self.text_inst = ax.text(x+1, y + 1, '', fontsize='small', fontweight='bold', clip_on = True )
        self.cid = fig.canvas.mpl_connect('button_press_event', self._onclick)
        self.expire_time = 0
        self.visible = True
        self.updated = False
        
    def set_properties(self, message):
        self.message, self.message_type = message, message['message_type']
        self.text_inst.set_text(message['display_text'])
        self.patch.set_visible(True)
        self.text_inst.set_visible(True)
        self.updated = False
        self.visible = True
        self.expire_time = time_utils.time() + 29.25
        message_type_params = MESSAGE_TYPES[self.message_type]
        self.text_inst.set_color(message_type_params['fg'])
        self.patch.set_facecolor(message_type_params['bg'])

    def update_text(self, display_text):
        self.text_inst.set_text(display_text)
        self.updated = True
        
    def hide(self):
        self.patch.set_visible(False)
        self.text_inst.set_text('')
        self.text_inst.set_visible(False)
        self.visible = False

    def _onclick(self, event):
        b, _ = self.patch.contains(event)
        if(b):
            self.onclick({'action': 'MESSAGE_CLICK', 'message':self.message})
    
class Gui:
    def __init__(self, config, on_click, history, console_print, get_band_info, waterfall_data):
        self.plt = plt
        self.fig = plt.figure(figsize = (10,5), facecolor=(.18, .71, .71, 0.4))
        self.fig.canvas.manager.set_window_title('PyFT8 by G1OJS')
        self.config, self.on_click, self.history, self.console_print, self.get_band_info  = config, on_click, history, console_print, get_band_info
        self.msg_box_display_queue = queue.Queue()
        self.msg_box_update_queue = queue.Queue()
        self.ax_wf = self.fig.add_axes([0,0,1,1], facecolor =(.18, .71, .71, 0.4))
        self.ax_wf.set_xticks([])
        self.ax_wf.set_yticks([])
        self.ax_wf.set_xlim(0,500)
        self.ax_wf.set_ylim(0,200)
        self.msg_boxes = {}
        self.metrics = []

    def enqueue_message_essentials(self, c):
        myCall = self.config['station']['call']
        message_type_value = 0 + 1*(c.msg_tuple[1] == myCall) + 2*(c.msg_tuple[0] == myCall) + 3*(c.msg_tuple[0].startswith('CQ') and not c.msg_tuple[1] == myCall)
        message_type = ['generic', 'from_me', 'to_me', 'CQ'][message_type_value]
        display_text = f"{' '.join(c.msg_tuple)}"
        if self.history:
            current_band = self.get_band_info()['current_band']
            geo_text = self.history.get_geo_text(c.msg_tuple[1], c.msg_tuple[2])
            wb_time = self.history.log_cache.get(c.msg_tuple[1],'') 
            wb_text = f"wb: {time_utils.format_duration(time_utils.time() - float(wb_time))}" if wb_time else ''
            hearing_me = '# ' if self.history.is_hearing_me(current_band, c.msg_tuple[1]) else ' '
            display_text = f"{' '.join(c.msg_tuple)} {hearing_me}{wb_text} {geo_text}"
            
        message = { 'message_type':message_type, 'cycle':c.origin['odd_even'],
                    'msg_tuple':c.msg_tuple, 'decode_completed':c.decode_completed,
                    'new_qso_info': {'call':c.msg_tuple[1], 'rst_sent': f"{c.snr:+03d}", 'grid_rpt':c.msg_tuple[2], 'my_tx_cycle': 1-c.origin['odd_even']},
                    'display_text': f"{' '.join(c.msg_tuple)}"}
        
        self.msg_box_display_queue.put(message)

    def after_new_search(self, curr_cycle):
        to_hide = [mb for mb in self.msg_boxes.values() if mb.visible and mb.cycle == curr_cycle]
        for mb in to_hide:
            mb.hide()
        if DO_METRICS:
            for l in self.metrics:
                print(l)
            self.metrics = []
             
    def run(self):
        self.plt.pause(0.1)
        
        while True:
            new_messages = []
            
            while not self.msg_box_display_queue.empty():
                message = self.msg_box_display_queue.get()
                new_messages.append(message)
                y = 200 - 9*len([m for m in self.msg_boxes.values() if m.visible])
                x = 200*message['cycle']
                if not y in self.msg_boxes:
                    self.msg_boxes[(x,y)] = Msg_box(self.fig, self.ax_wf, x, y, 180, 8, message, onclick = self.on_click)
                self.msg_boxes[(x,y)].set_properties(message)

            self.fig.canvas.draw()
            self.fig.canvas.flush_events()
            time_utils.sleep(0.05)
            if DO_METRICS:
                t0 = time_utils.cycle_time()
                for m in new_messages:
                    tdecode = m['decode_completed']
                    tdelay = (t0 - tdecode) %15
                    self.metrics.append(f"Screen updated {tdelay:5.2f}s after decode (at {tdecode:5.2f}) for {m['display_text']} ")






                    


        
