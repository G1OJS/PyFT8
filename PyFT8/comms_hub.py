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
global message_queue, loop

def queue_message(message):
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(message_queue.put(message), loop)
    else:
        print("⚠️ No running asyncio loop yet; message dropped:", message)

async def send_messages(websocket):
    while True:
        message = await message_queue.get()
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            print("Send error:", e)
        message_queue.task_done()

async def handle_client(websocket):
    # launch two coroutines: one for sending, one for receiving
    send_task = asyncio.create_task(send_messages(websocket))
    recv_task = asyncio.create_task(recv_commands(websocket))
    done, pending = await asyncio.wait(
        [send_task, recv_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
        
async def start_websockets_server():
    global message_queue, loop
    loop = asyncio.get_running_loop()
    message_queue = asyncio.Queue()
    events.subscribe("UI_message", queue_message)
    async with serve(handle_client, "localhost", 5678) as server:
        await server.serve_forever()

async def recv_commands(websocket):
    async for message in websocket:
        try:
            cmd = json.loads(message)
            cmd_type = cmd.get("type")
            print("Client command:", cmd)
            if cmd_type == "SetRxFreq":
                freq = cmd.get("freq")
                print(f"Change RX freq to {freq}")
              #  events.publish("SetRxFreq", freq)
            elif cmd_type == "SelectDecode":
                freq = cmd.get("freq")
                call = cmd.get("call")
             #   events.publish("SelectDecode", {"freq": freq, "call": call})
        except Exception as e:
            print("Bad command:", e, message)

