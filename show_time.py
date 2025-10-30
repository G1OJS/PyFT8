#!/usr/bin/env python

import asyncio
import datetime
import random
from PyFT8.comms_hub import config, events
from websockets.asyncio.server import serve



async def send_decodes(decodes):
    await websocket.send(decodes)

events.subscribe("AllDecodes", send_decodes)


    
#async def main():
#    async with serve(show_time, "localhost", 5678) as server:
#        await server.serve_forever()

#if __name__ == "__main__":
#    asyncio.run(main())
