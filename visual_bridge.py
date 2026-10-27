"""
Vaelkry Dev Labs - 3D Visualizer Real-Time State Bridge
Emits Discord Voice State transitions over local WebSocket (Port 8765)
"""

import asyncio
import json
import logging
import aiohttp
from aiohttp import web

logger = logging.getLogger("VaelkryDevLabs.VisualBridge")

class VisualBridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.app = web.Application()
        self.app.router.add_get("/ws", self.websocket_handler)
        self.runner = None

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.clients.add(ws)
        logger.info(f"Visualizer client connected. Total connected: {len(self.clients)}")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "ping":
                        await ws.send_str("pong")
        finally:
            self.clients.discard(ws)
            logger.info("Visualizer client disconnected.")
        return ws

    async def broadcast_state(self, bot_name: str, squad: str, action: str, target_zone: str):
        """
        Broadcasts bot movement payload to all open 3D dashboards.
        action: 'WORKING' | 'RESTING' | 'IDLE' | 'SLEEPING'
        """
        if not self.clients:
            return

        payload = json.dumps({
            "bot": bot_name,
            "squad": squad,
            "action": action,
            "target_zone": target_zone
        })
        tasks = [client.send_str(payload) for client in self.clients if not client.closed]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"Visual State Bridge active on ws://{self.host}:{self.port}/ws")