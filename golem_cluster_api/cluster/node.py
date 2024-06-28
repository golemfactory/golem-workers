import asyncio
import logging
from typing import List, Optional

from golem.resources import Activity, Network
from golem.utils.asyncio import create_task_with_logging, ensure_cancelled
from golem.utils.logging import get_trace_id_name
from golem_cluster_api.cluster.sidecars import Sidecar
from golem_cluster_api.context import WorkContext
from golem_cluster_api.models import State, ImportableCommand

logger = logging.getLogger(__name__)


class Node:
    """Self-contained element that represents cluster node."""

    def __init__(
        self,
        node_id: str,
        activity: Activity,
        node_ip: str,
        network: Network,
        on_start_commands: List[ImportableCommand],
        on_stop_commands: List[ImportableCommand],
        sidecars: List[Sidecar],
    ) -> None:
        self._node_id = node_id
        self._activity = activity
        self._node_ip = node_ip
        self._network = network
        self._on_start_commands = on_start_commands
        self._on_stop_commands = on_stop_commands
        self._sidecars = sidecars

        self._state = State.CREATED
        self._start_task: Optional[asyncio.Task] = None

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
                "Not scheduling start `%s` node, as it's already scheduled, running or stopping",
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
            logger.info("Not starting `%s` node, as it's already running or stopping", self)
            return

        logger.info("Starting `%s` node...", self)

        self._state = State.STARTING

        try:
            for command in self._on_start_commands:
                await self._run_command(command)
        except Exception:
            logger.exception("Starting failed!")
            self._state = State.STOPPED
            # TODO: handle stop / state cleanup. State cleanup should be in stages to accommodate different stages

            await self._stop_activity(self._activity)
            await self._activity.agreement.terminate()

            return

        for sidecar in self._sidecars:
            await sidecar.start(self)

        self._state = State.STARTED

        logger.info("Starting `%s` node done", self)

    async def stop(self) -> None:
        """Stop the node and cleanup its internal state."""

        if self._state not in (State.STARTING, State.STARTED):
            logger.info("Not stopping `%s` node, as it's already stopped", self)
            return

        logger.info("Stopping `%s` node...", self)

        self._state = State.STOPPING

        if self._start_task:
            await ensure_cancelled(self._start_task)
            self._start_task = None

        for sidecar in self._sidecars:
            await sidecar.stop()

        for command in self._on_stop_commands:
            await self._run_command(command)

        if not self._activity.destroyed:
            logger.warning("Activity should be destroyed in `on_stop_commands`!")

            await self._stop_activity(self._activity)

        await self._activity.agreement.terminate()

        self._activity = None

        self._state = State.STOPPED

        logger.info("Stopping `%s` node done", self)

    async def _stop_activity(self, activity: Activity) -> None:
        try:
            await activity.destroy()
        except Exception:
            logger.debug(f"Cannot destroy activity {activity}", exc_info=True)

    async def _run_command(self, command: ImportableCommand) -> None:
        command_func, command_args, command_kwargs = command.import_object()

        await command_func(
            WorkContext(
                activity=self._activity,
                extra={
                    "network": self._network,
                    "ip": self._node_ip,
                },
            ),
            *command_args,
            **command_kwargs,
        )
