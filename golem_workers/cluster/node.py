import asyncio
import logging
from typing import List, Optional, Callable, Awaitable, Mapping, MutableMapping, Tuple

from golem.node import GolemNode
from golem.resources import Activity, Network, BatchError
from golem.utils.asyncio import create_task_with_logging, ensure_cancelled
from golem.utils.logging import get_trace_id_name
from golem_workers.cluster.manager_stack import ManagerStack
from golem_workers.cluster.sidecars import Sidecar
from golem_workers.context import WorkContext
from golem_workers.models import (
    NodeState,
    ImportableWorkFunc,
    NodeConfig,
    MarketConfig,
    NodeNetworkConfig,
)

logger = logging.getLogger(__name__)


class Node:
    """Self-contained element that represents cluster node."""

    def __init__(
        self,
        golem_node: GolemNode,
        node_id: str,
        networks_config: Mapping[str, NodeNetworkConfig],
        node_config: NodeConfig,
        budget_type: str,
        node_type: str,
        networks: Mapping[str, Network],
        get_manager_stack: Callable[[MarketConfig, str, str, str], Awaitable[ManagerStack]],
    ) -> None:
        self._golem_node = golem_node
        self._node_id = node_id
        self._networks_config = networks_config
        self._node_config = node_config
        self._budget_type = budget_type
        self._node_type = node_type
        self._networks = networks
        self._get_manager_stack = get_manager_stack

        self._sidecars = self._prepare_sidecars()

        self._activity: Optional[Activity] = None
        self._network_ips: MutableMapping[str, str] = {}

        self._state = NodeState.CREATED
        self._background_task: Optional[asyncio.Task] = None

    def __str__(self) -> str:
        return self._node_id

    @property
    def node_id(self) -> str:
        """Read-only node id."""

        return self._node_id

    @property
    def state(self) -> NodeState:
        """Read-only node state."""

        return self._state

    def _prepare_sidecars(self) -> List[Sidecar]:
        sidecars = []

        for sidecar in self._node_config.sidecars:
            sidecar_class, sidecar_args, sidecar_kwargs = sidecar.import_object()
            sidecars.append(sidecar_class(self._golem_node, self, *sidecar_args, **sidecar_kwargs))

        return sidecars

    def schedule_provision(self) -> None:
        """Schedule provision of the node in another asyncio task."""

        if (self._background_task and not self._background_task.done()) or (
            self._state not in (NodeState.CREATED, NodeState.PROVISIONING_FAILED)
        ):
            logger.info(
                "Not scheduling provision `%s` node, as it's already provisioned",
                self,
            )
            return

        self._background_task = create_task_with_logging(
            self.provision(),
            trace_id=get_trace_id_name(self, "scheduled-provision"),
        )

    async def provision(self) -> None:
        logger.info("Provisioning `%s` node...", self)

        self._state = NodeState.PROVISIONING

        manager_stack = await self._get_manager_stack(
            self._node_config.market_config, self._budget_type, self._node_type, self._node_id
        )

        agreement = await manager_stack.get_agreement()
        agreement_data = await agreement.get_agreement_data()

        activity = await agreement.create_activity()

        self._activity = activity

        for network_name, node_network_config in self._networks_config.items():
            network = self._networks[network_name]
            node_id = await network.create_node(agreement_data.provider_id)
            self._network_ips[network_name] = node_id

        self._state = NodeState.PROVISIONED
        self._background_task = None

        self.schedule_start()  # TODO: Consider external place to start the node after provision

        logger.info("Provisioning `%s` node done", self)

    def schedule_start(self) -> None:
        """Schedule start of the node in another asyncio task."""

        if (self._background_task and not self._background_task.done()) or (
            self._state not in (NodeState.PROVISIONED, NodeState.STOPPED)
        ):
            logger.info(
                "Not scheduling start `%s` node, as it's already scheduled, running or stopping",
                self,
            )
            return

        self._background_task = create_task_with_logging(
            self.start(),
            trace_id=get_trace_id_name(self, "scheduled-start"),
        )

    async def start(self) -> None:
        """Start the node, its internal state and try to create its activity."""

        if self._state not in (NodeState.PROVISIONED, NodeState.STOPPED):
            logger.info("Not starting `%s` node, as it's already running or stopping", self)
            return

        logger.info("Starting `%s` node...", self)

        self._state = NodeState.STARTING

        try:
            for command in self._node_config.on_start_commands:
                await self._run_command(command)
        except Exception:
            logger.exception("Starting failed!")
            self._state = NodeState.STOPPED
            # TODO: handle stop / state cleanup. State cleanup should be in stages to accommodate different stages

            await self._stop_activity(self._activity)
            await self._activity.agreement.terminate()

            return

        for sidecar in self._sidecars:
            await sidecar.start()

        self._state = NodeState.STARTED
        self._background_task = None

        logger.info("Starting `%s` node done", self)

    async def stop(self) -> None:
        """Stop the node and cleanup its internal state."""

        if self._state not in (NodeState.STARTING, NodeState.STARTED):
            logger.info("Not stopping `%s` node, as it's already stopped", self)
            return

        logger.info("Stopping `%s` node...", self)

        self._state = NodeState.STOPPING

        if self._background_task:
            await ensure_cancelled(self._background_task)
            self._background_task = None

        for sidecar in self._sidecars:
            await sidecar.stop()

        for command in self._node_config.on_stop_commands:
            await self._run_command(command)

        if not self._activity.destroyed:
            logger.warning("Activity should be destroyed in `on_stop_commands`!")

            await self._stop_activity(self._activity)

        await self._activity.agreement.terminate()

        self._activity = None

        self._state = NodeState.STOPPED

        logger.info("Stopping `%s` node done", self)

    async def _stop_activity(self, activity: Activity) -> None:
        try:
            await activity.destroy()
        except Exception:
            logger.debug(f"Cannot destroy activity {activity}", exc_info=True)

    async def _run_command(self, command: ImportableWorkFunc) -> None:
        command_func, command_args, command_kwargs = command.import_object()

        logger.debug(f"Running `{command}`...")

        try:
            await command_func(
                WorkContext(
                    activity=self._activity, default_deploy_args=self._get_default_deploy_args()
                ),
                *command_args,
                **command_kwargs,
            )
        except BatchError as e:
            logger.debug(
                f"Running `{command}` failed!\n"
                f"stdout:\n"
                f"{[event.stdout for event in e.batch.events]}\n"
                f"stderr:\n"
                f"{[event.stderr for event in e.batch.events]}"
            )

            raise
        else:
            logger.debug(f"Running `{command}` done")

    def _get_default_deploy_args(self) -> Mapping:
        net_entries = []

        for network_name, node_network_config in self._networks_config.items():
            network, node_id = self.get_network(network_name)

            net_entries.append(network.deploy_args(node_id))

        return {
            "net": net_entries,
        }

    def get_network(self, network_name: str) -> Tuple[Network, Optional[str]]:
        """Return Network object correlated with given name and optionally assigned node ip."""

        network = self._networks[network_name]
        node_ip = self._network_ips.get(network_name)

        return network, node_ip
