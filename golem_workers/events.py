# golem_workers/events.py
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set, AsyncIterator
from dataclasses import dataclass, asdict


@dataclass
class NodeEvent:
    """Event emitted by a node."""

    node_id: str
    event_type: str
    timestamp: float
    data: Dict[str, Any]
    cluster_id: Optional[str] = None


class EventBus:
    """Central event bus for distributing events across the application."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.subscribers: Set[asyncio.Queue] = set()
        self.history: List[NodeEvent] = []
        self.history_limit = 1000  # Keep last 1000 events

    def emit(self, event: NodeEvent):
        """Emit an event to all subscribers."""
        # Add to history
        self.history.append(event)
        if len(self.history) > self.history_limit:
            self.history = self.history[-self.history_limit :]

        # Distribute to subscribers
        for queue in self.subscribers:
            queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to events."""
        queue = asyncio.Queue()
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def get_events(
        self,
        node_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> AsyncIterator[str]:
        """Get events as an async iterator, optionally filtered."""
        queue = self.subscribe()
        try:
            # First yield historical events that match the filter
            for event in self.history:
                if self._matches_filter(event, node_id, cluster_id, event_types):
                    yield self._format_sse_event(event)

            # Then yield new events as they come in
            while True:
                event = await queue.get()
                if self._matches_filter(event, node_id, cluster_id, event_types):
                    yield self._format_sse_event(event)
        finally:
            self.unsubscribe(queue)

    def _matches_filter(
        self,
        event: NodeEvent,
        node_id: Optional[str],
        cluster_id: Optional[str],
        event_types: Optional[List[str]],
    ) -> bool:
        """Check if an event matches the provided filters."""
        if node_id and event.node_id != node_id:
            return False
        if cluster_id and event.cluster_id != cluster_id:
            return False
        if event_types and event.event_type not in event_types:
            return False
        return True

    def _format_sse_event(self, event: NodeEvent) -> str:
        """Format an event as an SSE message."""
        data = json.dumps(asdict(event))
        return f"event: {event.event_type}\ndata: {data}\n\n"


# Global instance
event_bus = EventBus()


def emit_node_event(
    node_id: str, event_type: str, data: Dict[str, Any], cluster_id: Optional[str] = None
):
    """Emit a node event to the event bus."""
    event = NodeEvent(
        node_id=node_id,
        event_type=event_type,
        timestamp=time.time(),
        data=data,
        cluster_id=cluster_id,
    )
    event_bus.emit(event)
