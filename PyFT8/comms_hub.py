import os
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import webbrowser
import threading
import PyFT8.timers as timers


import threading
import traceback

def my_excepthook(args):
    print("Thread exception caught:\n",
          "".join(traceback.format_exception(args.exc_type,
                                             args.exc_value,
                                             args.exc_traceback)))
threading.excepthook = my_excepthook


def start_UI(UI_filename, UI_callback):
    threading.Thread(target=start_UI_page_server, daemon=True).start()
    threading.Thread(target=start_UI_ws_server, args=(UI_callback,)).start()
    webbrowser.open("http://localhost:8080/" + UI_filename)

#===================================================================================
# HTTP server for UI page
#===================================================================================
def start_UI_page_server():
    os.chdir(r"C:/Users/drala/Documents/Projects/GitHub/PyFT8/")
    server = ThreadingHTTPServer(("localhost", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()
    
#===================================================================================
# Python <-> JS communication via websockets
#===================================================================================
import asyncio
from websockets.asyncio.server import serve
global message_queue, loop, UI_callback
loop = None

def start_UI_ws_server(callback):
    global UI_callback
    import asyncio
    from websockets import serve
    timers.timedLog("Starting websockets server")
    UI_callback = callback
    async def ws_server():
        global message_queue, loop
        loop = asyncio.get_running_loop()
        message_queue = asyncio.Queue()
        async with serve(_handle_client, "localhost", 5678):
            await asyncio.Future()  # run forever
    asyncio.run(ws_server())

def send_to_ui_ws(topic, message, silent = True):
    if not isinstance(message, dict):
        message = {}    # should really raise exception here 
    if loop and loop.is_running():
        timers.timedLog(f"[WebsocketsServer] sending message with topic {topic}", silent = silent)
        full_message = {"topic": topic, **message}
        asyncio.run_coroutine_threadsafe(message_queue.put(full_message), loop)

async def _handle_client(websocket):
    # connection between here and the browser JS
    # launch two coroutines: one for sending, one for receiving
    send_task = asyncio.create_task(_send_queue_to_browser(websocket))
    recv_task = asyncio.create_task(_call_callback_on_rx_from_browser(websocket))
    done, pending = await asyncio.wait(
        [send_task, recv_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()

async def _send_queue_to_browser(websocket):
    while True:
        message = await message_queue.get()
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            timers.timedLog(f"[WebsocketsServer] couldn't send message", 'websockets.log')
        message_queue.task_done()

async def _call_callback_on_rx_from_browser(websocket):
    async for message in websocket:
        cmd = json.loads(message)
        UI_callback(cmd)

#===================================================================================
# Holds app config (globals)
#===================================================================================
import configparser
class Config:
    """
        modules needing data from here use 'from comms_hub import config'
    """
    def __init__(self):
        self.clearest_txfreq = 1000
        self.txfreq = 1000
        self.rxfreq = 1000
        self.bands = []
        self.myBand = False
        self.myFreq = False
        self.soundcards = {"input_device":["Microphone","CODEC"], "output_device":["Speaker", "CODEC"]}
        if(not self.check_config()):
            return
        parser = configparser.ConfigParser()
        parser.read("PyFT8.ini")
        self.myCall = parser.get("myStation","myCall")
        self.myGrid = parser.get("myStation","myGrid")

        input_search = parser.get("sound","soundcard_rx").split("_")
        self.soundcards.update({"input_device":input_search})
        output_search = parser.get("sound","soundcard_tx").split("_")
        self.soundcards.update({"output_device":output_search})

        self.decoder_search_limit = parser.get("decoder","candidate_search_limit")
        
        self.wsjtx_all_file = parser.get("paths","wsjtx_all_file")

        self.decoder = parser.get("options","decoder")

        for band_name, band_freq in parser.items("bands"):
            self.bands.append({"band_name":band_name, "band_freq":band_freq})

    def check_config(self):
        if(os.path.exists("PyFT8.ini")):
            return True
        else:
            print("No PyFT8.ini in current directory.")
            txt = "[myStation]\nmyCall = please edit this e.g. myCall = G1OJS "
            txt += "\nmyGrid = please edit this e.g. myGrid = IO90"
            txt += "\n"
            with open("PyFT8.ini","w") as f:
                f.write(txt)
            print("A blank PyFT8.ini file has been created - please edit it and re=run")

    def update_clearest_txfreq(self, clear_freq):
        self.clearest_txfreq = clear_freq
        send_to_ui_ws("set_txfreq", {'freq':str(self.clearest_txfreq)})
    
config = Config()


