import asyncio
import logging
from typing import Dict, Mapping, Optional, List

from golem.resources import Activity, Network
from golem.utils.asyncio import create_task_with_logging
from golem.utils.logging import get_trace_id_name

from golem_cluster_api.cluster.node import Node
from golem_cluster_api.models import NodeConfig, PaymentConfig, State, Command

logger = logging.getLogger(__name__)


class Cluster:
    """Top-level element that is responsible for maintaining all components for single cluster."""

    def __init__(
        self,
        cluster_id: str,
        network: Network,
        payment_config: Optional[PaymentConfig] = None,
        node_types: Optional[Mapping[str, NodeConfig]] = None,
    ) -> None:
        super().__init__()

        self._cluster_id = cluster_id
        self.network = network

        self._payment_config = payment_config or PaymentConfig()
        self._node_types = node_types or {}

        self._nodes: Dict[str, Node] = {}
        self._nodes_id_counter = 0
        self._start_task: Optional[asyncio.Task] = None

        self._state: State = State.CREATED

    def __str__(self) -> str:
        return self._cluster_id

    @property
    def cluster_id(self) -> str:
        """Read-only cluster id."""

        return self._cluster_id

    @property
    def state(self) -> State:
        """Read-only cluster state."""

        return self._state

    @property
    def nodes(self) -> Mapping[str, Node]:
        """Read-only map of named nodes.

        Nodes will persist in the collection even after they are terminated."""

        return self._nodes

    def schedule_start(self) -> None:
        """Schedule start of the node in another asyncio task."""

        if (self._start_task and not self._start_task.done()) or (
            self._state not in (State.CREATED, State.STOPPED)
        ):
            logger.info(
                "Ignoring start scheduling request, as `%s` is not in created or stopped state but it is in `%s` "
                "state",
                self,
                self._state,
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

    async def stop(self) -> None:
        """Stop the cluster."""

        if self._state is not State.STARTED:
            logger.info("Not stopping `%s` cluster as it's already stopped or stopping", self)
            return

        logger.info("Stopping `%s` cluster...", self)

        self._state = State.STOPPING

        await asyncio.gather(*[node.stop() for node in self._nodes.values()])

        self._state = State.STOPPED
        self._nodes.clear()
        self._nodes_id_counter = 0

        logger.info("Stopping `%s` cluster done", self)

    def is_running(self) -> bool:
        return self._state != State.STOPPED

    def _get_new_node_id(self) -> str:
        node_id = f"node{self._nodes_id_counter}"
        self._nodes_id_counter += 1
        return node_id

    def get_node_type_config(self, node_type: str) -> NodeConfig:
        return self._node_types.get(node_type, NodeConfig())

    def create_node(
        self,
        activity: Activity,
        node_ip,
        on_start_commands: List[Command] = None,
        on_stop_commands: List[Command] = None,
    ) -> Node:
        node_id = self._get_new_node_id()

        self._nodes[node_id] = node = Node(
            node_id,
            activity,
            node_ip,
            self.network,
            on_start_commands=on_start_commands,
            on_stop_commands=on_stop_commands,
        )

        node.schedule_start()

        return node

    async def delete_node(self, node: Node) -> None:
        # TODO: use schedule stop and remove instead of inline waiting
        await node.stop()

        del self._nodes[node.node_id]
