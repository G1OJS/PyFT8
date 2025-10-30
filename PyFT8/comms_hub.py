import os
import json

class Config:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                return json.load(f)
        return {"txFreq": 2000, "rxFreq": 2000}

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=2)

class Events:
    def __init__(self):
        self.subs = {}  # dict: topic -> list of subscriber callbacks

    def subscribe(self, topic, fn):
        self.subs.setdefault(topic, []).append(fn)

    def publish(self, topic, data):
        for fn in self.subs.get(topic, []):
            fn(data)

events = Events()
config = Config()

import asyncio
import datetime
import threading
from PyFT8.comms_hub import config, events
from websockets.asyncio.server import serve
global decode_queue, loop
decode_queue = asyncio.Queue() 

def update_decodes(new_decode):
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(decode_queue.put(new_decode), loop)
    else:
        print("⚠️ No running asyncio loop yet; decode dropped:", new_decode)

async def send_decodes(websocket):
    while True:
        new_decode = await decode_queue.get() 
        await websocket.send(json.dumps(new_decode))
        decode_queue.task_done()
        
async def start_websockets_server():
    global decode_queue, loop
    loop = asyncio.get_running_loop()
    decode_queue = asyncio.Queue()
    events.subscribe("AllDecodes", update_decodes)
    async with serve(send_decodes, "localhost", 5678) as server:
        await server.serve_forever()


