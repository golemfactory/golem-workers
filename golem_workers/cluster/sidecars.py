import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio.subprocess import Process
from typing import TYPE_CHECKING, Optional, Sequence

from golem.utils.asyncio import create_task_with_logging, ensure_cancelled
from golem.utils.logging import get_trace_id_name

from golem_workers.utils import run_subprocess, get_ssh_proxy_command, get_connection_uri

if TYPE_CHECKING:
    from golem_workers.cluster.node import Node

logger = logging.getLogger(__name__)


class Sidecar(ABC):
    """Base class for companion business logic that runs in relation to the node."""

    def __init__(self, node: "Node") -> None:
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


class PortTunnelSidecar(Sidecar, ABC):
    """Sidecar that runs a generic tunnel between the related node and the local machine.

    Warning will be generated if tunnel exists prematurely.
    """

    def __init__(
        self,
        node: "Node",
        *,
        local_port: int,
        remote_port: Optional[int] = None,
    ) -> None:
        super().__init__(node)

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


class SshPortTunnelSidecar(PortTunnelSidecar):
    """Sidecar that runs ssh tunnel from the local machine the related node.

    Warning will be generated if tunnel exists prematurely.
    """

    def __init__(
        self,
        node: "Node",
        *,
        ssh_private_key_path: str,
        reverse: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(node, **kwargs)

        self._ssh_private_key_path = ssh_private_key_path
        self._reverse = reverse

    def _get_subprocess_args(self) -> Sequence:
        ssh_proxy_command = get_ssh_proxy_command(
            get_connection_uri(self._node._network, self._node._node_ip),
            self._node._network.node.app_key,
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

    Warning will be generated if tunnel exists prematurely.
    """

    def _get_subprocess_args(self) -> Sequence:
        return [
            "websocat",
            f"tcp-listen:0.0.0.0:{self._local_port}",
            "{}/{}".format(
                get_connection_uri(self._node._network, self._node._node_ip), self._remote_port
            ),
            f"-H=Authorization:Bearer {self._node._network.node.app_key}",
            "--binary",
        ]
