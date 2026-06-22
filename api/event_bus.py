"""Simple async event bus for Server-Sent Events."""

import asyncio
from collections import defaultdict
from typing import Dict, List, Any


class EventBus:
    """Simple pub/sub event bus for SSE streaming."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, channel: str) -> asyncio.Queue:
        """Subscribe to a channel. Returns the queue for this subscriber."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[channel].append(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        """Unsubscribe a queue from a channel."""
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(q)
            except ValueError:
                pass  # Already removed

    def publish(self, channel: str, event: Dict[str, Any]) -> None:
        """Publish an event to all subscribers of a channel."""
        for q in self._subscribers.get(channel, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop event if queue is full


# Global event bus instance
event_bus = EventBus()
