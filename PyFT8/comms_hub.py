import os
import json
import PyFT8.timers as timers

#===================================================================================
# Messaging system for messeges between functions Python <-> JS (via websockets)
#===================================================================================
from types import SimpleNamespace

TOPICS = SimpleNamespace(
    decoder = SimpleNamespace(
        decoding_started    = "decoder.decoding_started",       # used by UI to clear windows etc      
        decode_dict         = "decoder.decode_dict",            # used by UI
        decode_all_txt_line = "decoder.decode_all_txt_line",    # used by tests
        decode_dict_rxfreq  = "decoder.decode_dict_rxfreq",     # used by UI and QSO sequencer
        decoding_completed  = "decoder.decoding_completed",     # used by tests to count matches
    ),
    ui = SimpleNamespace(
        send_cq         = "ui.send_cq",
        reply_to_cq     = "ui.reply_to_cq",
        reply_to_message= "ui.reply_to_message",
        set_rxfreq      = "ui.set_rxfreq",
    ),
    config = SimpleNamespace(
        rxfreq_changed  = "config.rxfreq_changed",
    )
)

all_topics = {
    value
    for ns in vars(TOPICS).values()
    if isinstance(ns, SimpleNamespace)
    for value in vars(ns).values()
}

class Events:
    def __init__(self):
        self.subscriber_callbacks = {} 

    def subscribe(self, topic, subs_cb):
        self.subscriber_callbacks.setdefault(topic, []).append(subs_cb)

    def publish(self, topic, data):
        if topic not in all_topics:
            timers.timedLog(f"[Events] Unrecognised topic '{topic}' — ignored", logfile = "events.log", silent = True)
            return
        subs_cbs = self.subscriber_callbacks.get(topic, [])
        if not subs_cbs:
            timers.timedLog(f"[Events] {topic} published {data!r} — no subscribers", logfile = 'events.log', silent = True)
        for subs_cb in subs_cbs:
            timers.timedLog(f"[Events] {topic} to {subs_cb.__name__}({data!r})", logfile = 'events.log', silent = True)
            subs_cb(data)
            
# modules needing this use 'from comms_hub import events' :
events = Events()


#===================================================================================
# Python <-> JS communication via websockets
#===================================================================================
import asyncio
import datetime
import threading
from websockets.asyncio.server import serve
global message_queue, loop

async def start_websockets_server():
    global message_queue, loop
    loop = asyncio.get_running_loop()
    message_queue = asyncio.Queue()
    events.subscribe(TOPICS.decoder.decoding_started, lambda msg: _queue_message(TOPICS.decoder.decoding_started, msg))
    events.subscribe(TOPICS.decoder.decode_dict, lambda msg: _queue_message(TOPICS.decoder.decode_dict, msg))
    events.subscribe(TOPICS.decoder.decode_dict_rxfreq, lambda msg: _queue_message(TOPICS.decoder.decode_dict_rxfreq, msg))
    events.subscribe(TOPICS.config.rxfreq_changed, lambda msg: _queue_message(TOPICS.config.rxfreq_changed, msg))
    async with serve(_handle_client, "localhost", 5678) as server:
        await server.serve_forever()

def _queue_message(topic, message):
    if not isinstance(message, dict):
        message = {}    # should really raise exception here 
    if loop and loop.is_running():
        full_message = {"topic": topic, **message}
        asyncio.run_coroutine_threadsafe(message_queue.put(full_message), loop)
    else:
        print("No running asyncio loop yet; message dropped:", message)

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
        timers.timedLog(f"[WebsocketsServer] sending {message}", 'events.log')
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            timers.timedLog(f"[WebsocketsServer] couldn't send message", 'events.log')
        message_queue.task_done()

async def _receive_from_browser(websocket):
    async for message in websocket:
        cmd = json.loads(message)
        events.publish(cmd["topic"], cmd)


#===================================================================================
# Store / read persistent app config to/from a config file
#===================================================================================
class Config:
    def __init__(self, filename="config.json"):
        # needs writing so that config.json takes precedence over constants
        self.filename = filename
        self.data = {"rxfreq": 2000, "txfreq":2000,
                     "input_device":["Microphone","CODEC"], "output_device":["Speaker", "CODEC"]}
      #  if os.path.exists(self.filename):
      #      with open(self.filename) as f:
      #          self.data = json.load(f)
        events.subscribe(TOPICS.ui.set_rxfreq, self.set_rxFreq)
        
    def set_rxFreq(self, cmd):
        self.data['rxfreq'] = int(cmd['freq'])
       # self.save()
        events.publish(TOPICS.config.rxfreq_changed, {'freq':int(self.data['rxfreq'])})
        
    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=2)
            
# modules needing this use 'from comms_hub import config' :
config = Config()
