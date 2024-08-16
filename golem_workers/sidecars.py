import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio.subprocess import Process
from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Sequence, Callable
from yarl import URL

from golem.node import GolemNode
from golem.utils.asyncio import create_task_with_logging, ensure_cancelled
from golem.utils.asyncio.tasks import resolve_maybe_awaitable
from golem.utils.logging import get_trace_id_name
from golem.utils.typing import MaybeAwaitable
from golem_workers.utils import run_subprocess, get_ssh_proxy_command, get_connection_uri

if TYPE_CHECKING:
    from golem_workers.cluster.node import Node

logger = logging.getLogger(__name__)


class Sidecar(ABC):
    """Base class for companion business logic that runs in relation to the node."""

    def __init__(self, golem_node: GolemNode, node: "Node") -> None:
        self._golem_node = golem_node
        self._node = node

    @abstractmethod
    async def start(self) -> None:
        """Start the sidecar and its internal state."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the sidecar and cleanup its internal state."""
        ...

    @abstractmethod
    async def is_running(self) -> bool:
        """Check if the sidecar is running."""
        ...


class MonitorClusterNodeSidecar(Sidecar, ABC):
    """Base class for companion business logic that monitor the state of the related node."""

    name = "<unnamed>"

    def __init__(
        self,
        golem_node: GolemNode,
        node: "Node",
        *,
        on_monitor_failed_func: Callable[["MonitorClusterNodeSidecar"], MaybeAwaitable[None]],
    ):
        super().__init__(golem_node, node)

        self._on_monitor_check_failed_func = on_monitor_failed_func

        self._monitor_task: Optional[asyncio.Task] = None

    def __str__(self) -> str:
        return f"{self.name} monitor"

    @abstractmethod
    async def _monitor(self) -> None: ...

    async def start(self) -> None:
        """Start the sidecar and its internal state."""

        if self.is_running():
            logger.info(f"Not starting `%s` node {self}, as it's already running", self._node)
            return

        logger.info(f"Starting `%s` node {self}...", self._node)

        self._monitor_task = create_task_with_logging(
            self._monitor(), trace_id=get_trace_id_name(self, self._get_monitor_task_name())
        )

        logger.info(f"Starting `%s` node {self} done", self._node)

    async def stop(self) -> None:
        """Stop the sidecar and cleanup its internal state."""

        if not self.is_running():
            logger.info(f"Not stopping `%s` node {self}, as it's already stopped", self._node)
            return

        logger.info(f"Stopping `%s` node {self}...", self._node)

        await ensure_cancelled(self._monitor_task)
        self._monitor_task = None

        logger.info(f"Stopping `%s` node {self} done", self._node)

    def is_running(self) -> bool:
        """Check if the sidecar is running."""

        return self._monitor_task and not self._monitor_task.done()

    def _handle_monitor_check_failure(self) -> None:
        logger.debug(f"`%s` node {self} check failed, monitor will stop", self._node)

        create_task_with_logging(
            resolve_maybe_awaitable(self._on_monitor_check_failed_func(self)),
            trace_id=get_trace_id_name(self, "on-monitor-check-failed"),
        )

    def _get_monitor_task_name(self) -> str:
        return "{}-{}".format(self._node, str(self).replace(" ", "-"))


class ActivityStateMonitorClusterNodeSidecar(MonitorClusterNodeSidecar):
    """Sidecar that monitor the activity state of the related node.

    External callback will be called if the activity enters non-working state.
    """

    name = "activity"

    def __init__(
        self, golem_node: GolemNode, node: "Node", *, check_interval: timedelta, **kwargs
    ) -> None:
        super().__init__(golem_node, node, **kwargs)

        self._check_interval = check_interval

    async def _monitor(self) -> None:
        while True:
            activity_state = await self._node.activity.get_state()

            if (
                "Terminated" in activity_state.state
                or "Unresponsive" in activity_state.state
                or activity_state.error_message is not None
            ):
                self._handle_monitor_check_failure()

                return

            await asyncio.sleep(self._check_interval.total_seconds())


class PortTunnelSidecar(Sidecar, ABC):
    """Sidecar that runs a generic tunnel between the related node and the local machine.

    Warning will be generated if tunnel exists prematurely.
    """

    def __init__(
        self,
        golem_node: GolemNode,
        node: "Node",
        *,
        network_name: str,
        local_port: int,
        remote_port: Optional[int] = None,
    ) -> None:
        super().__init__(golem_node, node)

        self._network_name = network_name
        self._local_port = local_port
        self._remote_port = remote_port or local_port

        self._tunnel_process: Optional[Process] = None
        self._early_exit_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the sidecar and its internal state."""

        if self.is_running():
            logger.info(
                "Not starting `%s` node `%s` tunnel, as it's already running",
                self._node,
                self._get_tunel_type(),
            )
            return

        logger.info("Starting `%s` node `%s` tunnel...", self._node, self._get_tunel_type())

        args = self._get_subprocess_args()

        self._tunnel_process = await run_subprocess(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._early_exit_task = create_task_with_logging(
            self._on_tunnel_early_exit(),
            trace_id=get_trace_id_name(self, f"{self._get_tunel_type()}-early-exit"),
        )

        logger.info("Starting `%s` node `%s` tunnel done", self._node, self._get_tunel_type())

    async def stop(self) -> None:
        """Stop the sidecar and cleanup its internal state."""

        if not self.is_running():
            logger.info(
                "Not stopping `%s` node `%s` tunnel, as it's not running",
                self._node,
                self._get_tunel_type(),
            )
            return

        logger.info("Stopping `%s` node `%s` tunnel...", self._node, self._get_tunel_type())

        await ensure_cancelled(self._early_exit_task)
        self._early_exit_task = None

        self._tunnel_process.terminate()
        await self._tunnel_process.wait()

        self._tunnel_process = None

        logger.info("Stopping `%s` node `%s` tunnel done", self._node, self._get_tunel_type())

    def is_running(self) -> bool:
        """Check if the sidecar is running."""

        return self._tunnel_process and self._tunnel_process.returncode is None

    async def _on_tunnel_early_exit(self) -> None:
        await self._tunnel_process.communicate()

        logger.warning(
            "`%s` node %s exited prematurely!",
            self._node,
            self._get_tunel_type(),
        )

    def _get_tunel_type(self) -> str:
        return ":{}->:{}".format(self._local_port, self._remote_port)

    @abstractmethod
    def _get_subprocess_args(self) -> Sequence: ...

    def _get_network_connection_uri(self) -> URL:
        network, node_ip = self._node.get_network(self._network_name)
        return get_connection_uri(network, node_ip)


class SshPortTunnelSidecar(PortTunnelSidecar):
    """Sidecar that runs ssh tunnel from the local machine the related node.

    Note that this sidecar requires `ssh` binary available on the requestor.
    Warning will be generated if tunnel exists prematurely.
    """

    def __init__(
        self,
        golem_node: GolemNode,
        node: "Node",
        *,
        ssh_private_key_path: str,
        reverse: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(golem_node, node, **kwargs)

        self._ssh_private_key_path = ssh_private_key_path
        self._reverse = reverse

    def _get_subprocess_args(self) -> Sequence:
        ssh_proxy_command = get_ssh_proxy_command(
            self._get_network_connection_uri(),
            self._golem_node.app_key,
        )

        return [
            "ssh",
            "-N",
            "-R" if self._reverse else "-L",
            f"*:{self._remote_port}:127.0.0.1:{self._local_port}",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            f"ProxyCommand={ssh_proxy_command}",
            "-i",
            self._ssh_private_key_path,
            f"root@{str(self._node.node_id)}",
        ]

    def _get_tunel_type(self) -> str:
        return ":{}{}:{}".format(
            self._local_port, "<-" if self._reverse else "->", self._remote_port
        )


class WebsocatPortTunnelSidecar(PortTunnelSidecar):
    """Sidecar that runs websocat tunnel from the local machine to the related node.

    Note that this sidecar requires `websocat` binary available on the requestor.
    Warning will be generated if tunnel exists prematurely.
    """

    def _get_subprocess_args(self) -> Sequence:
        return [
            "websocat",
            f"tcp-listen:0.0.0.0:{self._local_port}",
            f"{self._get_network_connection_uri()}/{self._remote_port}",
            f"-H=Authorization:Bearer {self._golem_node.app_key}",
            "--binary",
        ]
