import asyncio
import logging
from typing import (
    Callable,
    Dict,
    Mapping,
    Optional,
    Any,
)

from golem.utils.asyncio import create_task_with_logging
from golem.utils.asyncio.tasks import resolve_maybe_awaitable
from golem.utils.logging import get_trace_id_name
from golem.utils.typing import MaybeAwaitable
from golem_cluster_api.models import PaymentConfig, State

logger = logging.getLogger(__name__)


class Cluster:
    """Top-level element that is responsible for maintaining all components for single cluster."""

    def __init__(
        self,
        name: str,
        payment_config: Optional[PaymentConfig] = None,
        node_types: Optional[Mapping[str, Any]] = None,
        on_stop: Optional[Callable[["Cluster"], MaybeAwaitable[None]]] = None,
    ) -> None:
        super().__init__()

        self._name = name
        self._payment_config = payment_config or PaymentConfig()
        self._node_types = node_types or {}
        self._on_stop = on_stop

        self._nodes: Dict[str, Any] = {}
        self._nodes_id_counter = 0
        self._start_task: Optional[asyncio.Task] = None

        self._state: State = State.CREATED

    def __str__(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        """Read-only cluster name."""

        return self._name

    @property
    def state(self) -> State:
        """Read-only cluster state."""

        return self._state

    @property
    def nodes(self) -> Mapping[str, Any]:
        """Read-only map of named nodes.

        Nodes will persist in the collection even after they are terminated."""

        return self._nodes

    def schedule_start(self) -> None:
        """Schedule start of the node in another asyncio task."""

        if (self._start_task and not self._start_task.done()) or (
            self._state not in (State.CREATED, State.STOPPED)
        ):
            logger.info(
                f"Ignoring start scheduling request, as `%s` is not in created or stopped state but it is in `%s` "
                f"state",
                self, self._state
            )
            return

        self._start_task = create_task_with_logging(
            self.start(),
            trace_id=get_trace_id_name(self, "scheduled-start"),
        )

    async def start(self) -> None:
        """Start the cluster and its internal state."""

        if self._state not in (State.CREATED, State.STOPPED):
            logger.info("Not starting `%s` cluster as it's already running or starting", self)
            return

        logger.info("Starting `%s` cluster...", self)

        self._state = State.STARTED

        logger.info("Starting `%s` cluster done", self)

    async def stop(self, call_events: bool = True) -> None:
        """Stop the cluster."""

        if self._state in (State.STARTED,):
            logger.info("Not stopping `%s` cluster as it's already stopped or stopping", self)
            return

        logger.info("Stopping `%s` cluster...", self)

        self._state = State.STOPPING

        await asyncio.gather(*[node.stop(call_events=False) for node in self._nodes.values()])

        self._state = State.STOPPED
        self._nodes.clear()
        self._nodes_id_counter = 0

        if self._on_stop and call_events:
            create_task_with_logging(
                resolve_maybe_awaitable(self._on_stop(self)),
                trace_id=get_trace_id_name(self, "on-stop"),
            )

        logger.info("Stopping `%s` cluster done", self)

    def is_running(self) -> bool:
        return self._state != State.STOPPED
