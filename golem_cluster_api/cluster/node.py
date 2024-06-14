import asyncio
import logging
from typing import Callable, Optional

from golem.resources import Activity
from golem.utils.asyncio import create_task_with_logging, ensure_cancelled
from golem.utils.asyncio.tasks import resolve_maybe_awaitable
from golem.utils.logging import get_trace_id_name
from golem.utils.typing import MaybeAwaitable
from golem_cluster_api.models import State

logger = logging.getLogger(__name__)


class Node:
    """Self-contained element that represents cluster node."""

    def __init__(
        self,
        node_id: str,
        activity: Activity,
        on_stop: Optional[Callable[["Node"], MaybeAwaitable[None]]] = None,
    ) -> None:
        self._node_id = node_id
        self._activity = activity
        self._on_stop = on_stop

        self._state = State.CREATED
        self._start_task: Optional[asyncio.Task] = None
        self._on_stop: Optional[Callable[["Node"], MaybeAwaitable[None]]] = None

    def __str__(self) -> str:
        return self._node_id

    @property
    def node_id(self) -> str:
        """Read-only node id."""

        return self._node_id

    @property
    def state(self) -> State:
        """Read-only node state."""

        return self._state

    def schedule_start(self) -> None:
        """Schedule start of the node in another asyncio task."""

        if (self._start_task and not self._start_task.done()) or (
            self._state not in (State.CREATED, State.STOPPED)
        ):
            logger.info(
                f"Not scheduling start `%s` node, as it's already scheduled, running or stopping",
                self,
            )
            return

        self._start_task = create_task_with_logging(
            self.start(),
            trace_id=get_trace_id_name(self, "scheduled-start"),
        )

    async def start(self) -> None:
        """Start the node, its internal state and try to create its activity."""

        if self._state not in (State.CREATED, State.STOPPED):
            logger.info(f"Not starting `%s` node, as it's already running or stopping", self)
            return

        logger.info("Starting `%s` node...", self)

        self._state = State.STARTING

        # setup commands

        self._state = State.STARTED

        logger.info("Starting `%s` node done", self)

    async def stop(self, call_events: bool = True) -> None:
        """Stop the node and cleanup its internal state."""

        if self._state is not State.STARTED:
            logger.info(f"Not stopping `%s` node, as it's already stopped", self)
            return

        logger.info("Stopping `%s` node...", self)

        self._state = State.STOPPING

        if self._start_task:
            await ensure_cancelled(self._start_task)
            self._start_task = None

        if self._activity:
            await self._stop_activity(self._activity)
            self._activity = None

        self._state = State.STOPPED

        if self._on_stop and call_events:
            create_task_with_logging(
                resolve_maybe_awaitable(self._on_stop(self)),
                trace_id=get_trace_id_name(self, "on-stop"),
            )

        logger.info("Stopping `%s` node done", self)

    async def _stop_activity(self, activity: Activity) -> None:
        try:
            await activity.destroy()
        except Exception:
            logger.debug(f"Cannot destroy activity {activity}", exc_info=True)
