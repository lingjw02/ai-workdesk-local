import asyncio
import json
import logging
from typing import Set, Dict, Any, Callable, List
from fastapi import WebSocket

logger = logging.getLogger("EventBus")


class EventBus:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._subscribers: Dict[str, List[Callable]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected WebSockets and trigger internal listeners."""
        payload = {
            "type": event_type,
            "data": data,
        }
        text = json.dumps(payload, default=str)
        dead = set()
        for conn in self.active_connections:
            try:
                await conn.send_text(text)
            except Exception:
                dead.add(conn)
        for d in dead:
            self.active_connections.discard(d)

        # Trigger internal in-process subscribers
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(data))
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in subscriber handler for {event_type}: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)


event_bus = EventBus()
