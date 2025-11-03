import os
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import webbrowser
import threading
import PyFT8.timers as timers

def start_UI(UI_callback):
    threading.Thread(target=start_UI_page_server, daemon=True).start()
    threading.Thread(target=start_UI_ws_server, args=(UI_callback,)).start()
    webbrowser.open("http://localhost:8080/UI.html")

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

async def start_websockets_server():
    global message_queue, loop
    loop = asyncio.get_running_loop()
    message_queue = asyncio.Queue()
    async with serve(_handle_client, "localhost", 5678) as server:
        await server.serve_forever()

def send_to_ui_ws(topic, message):
    if not isinstance(message, dict):
        message = {}    # should really raise exception here 
    if loop and loop.is_running():
        full_message = {"topic": topic, **message}
        asyncio.run_coroutine_threadsafe(message_queue.put(full_message), loop)

async def _handle_client(websocket):
    # connection between here and the browser JS
    # launch two coroutines: one for sending, one for receiving
    send_task = asyncio.create_task(_send_to_browser(websocket))
    recv_task = asyncio.create_task(_receive_from_browser(websocket))
    done, pending = await asyncio.wait(
        [send_task, recv_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()

async def _send_to_browser(websocket):
    while True:
        message = await message_queue.get()
        timers.timedLog(f"[WebsocketsServer] sending {message}", 'websockets.log')
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            timers.timedLog(f"[WebsocketsServer] couldn't send message", 'websockets.log')
        message_queue.task_done()

async def _receive_from_browser(websocket):
    async for message in websocket:
        cmd = json.loads(message)
        try:
            UI_callback(cmd)
        except Exception as e:
            timers.timedLog(f"[WebSockets] callback {UI_callback.__name__} failed: {e}", 'websockets.log')


#===================================================================================
# Holds app config (globals)
#===================================================================================
class Config:
    """
        modules needing data from here use 'from comms_hub import config'
    """
    def __init__(self):
        self.clearest_txfreq = [0,0]
        self.txfreq = 0;
        self.rxfreq = 0;
        self.data = {"input_device":["Microphone","CODEC"], "output_device":["Speaker", "CODEC"]}
        
    def update_clearest_txfreq(self, clear_freq):
        self.clearest_txfreq[0] = self.clearest_txfreq[-1]
        self.clearest_txfreq[-1] = clear_freq
        send_to_ui_ws("set_txfreq", {'freq':str(self.clearest_txfreq[-1])})
    
config = Config()


#===================================================================================
# Clear log files
#===================================================================================
#logs = ['QSO.log', 'PyFT8.log']
logs_to_clear = ['PyFT8.log']
for l in logs_to_clear:
    with open(l, 'w') as f:
        f.write('')
