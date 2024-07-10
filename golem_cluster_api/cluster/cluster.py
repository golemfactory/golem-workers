import asyncio
import hashlib
import logging
from typing import Dict, Mapping, Optional

from golem.node import GolemNode
from golem.resources import Network
from golem.utils.asyncio import create_task_with_logging
from golem.utils.logging import get_trace_id_name
from golem_cluster_api.budgets import Budget
from golem_cluster_api.cluster.manager_stack import ManagerStack

from golem_cluster_api.cluster.node import Node
from golem_cluster_api.golem import DriverListAllocationPaymentManager
from golem_cluster_api.models import (
    NodeConfig,
    PaymentConfig,
    BudgetConfig,
    BudgetScope,
    ClusterState,
    MarketConfig,
)

logger = logging.getLogger(__name__)


class Cluster:
    """Top-level element that is responsible for maintaining all components for single cluster."""

    def __init__(
        self,
        golem_node: GolemNode,
        cluster_id: str,
        network: Network,
        payment_config: Optional[PaymentConfig] = None,
        node_types: Optional[Mapping[str, NodeConfig]] = None,
        budget_types: Optional[Mapping[str, BudgetConfig]] = None,
    ) -> None:
        self._golem_node = golem_node
        self._cluster_id = cluster_id
        self.network = network

        self._payment_config = payment_config or PaymentConfig()
        self._node_types = node_types or {}
        self._budget_types = budget_types or {}

        self._manager_stacks: Dict[str, ManagerStack] = {}
        self._budgets: Dict[str, Budget] = {}
        self._nodes: Dict[str, Node] = {}
        self._nodes_id_counter = 0
        self._start_task: Optional[asyncio.Task] = None
        self.payment_manager = DriverListAllocationPaymentManager(
            network.node,
            budget=5,  # FIXME: use config / generic budget control,
            network=payment_config.network,
            driver=payment_config.driver,
        )

        self._state: ClusterState = ClusterState.CREATED
        self._extra = {}

    def __str__(self) -> str:
        return self._cluster_id

    @property
    def cluster_id(self) -> str:
        """Read-only cluster id."""

        return self._cluster_id

    @property
    def state(self) -> ClusterState:
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
            self._state not in (ClusterState.CREATED, ClusterState.STOPPED)
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

        if self._state not in (ClusterState.CREATED, ClusterState.STOPPED):
            logger.info("Not starting `%s` cluster as it's already running or starting", self)
            return

        logger.info("Starting `%s` cluster...", self)

        await self.payment_manager.start()

        self._state = ClusterState.STARTED

        logger.info("Starting `%s` cluster done", self)

    async def stop(self) -> None:
        """Stop the cluster."""

        if self._state is not ClusterState.STARTED:
            logger.info("Not stopping `%s` cluster as it's already stopped or stopping", self)
            return

        logger.info("Stopping `%s` cluster...", self)

        self._state = ClusterState.STOPPING

        await asyncio.gather(*[node.stop() for node in self._nodes.values()])
        await asyncio.gather(
            *[manager_stack.stop() for manager_stack in self._manager_stacks.values()]
        )
        await asyncio.gather(*[budget.stop() for budget in self._budgets.values()])

        await self.payment_manager.stop()

        self._state = ClusterState.STOPPED
        self._nodes.clear()
        self._manager_stacks.clear()
        self._budgets.clear()
        self._nodes_id_counter = 0

        logger.info("Stopping `%s` cluster done", self)

    def is_running(self) -> bool:
        return self._state != ClusterState.STOPPED

    def _get_new_node_id(self) -> str:
        node_id = f"node{self._nodes_id_counter}"
        self._nodes_id_counter += 1
        return node_id

    def get_node_type_config(self, node_type: str) -> NodeConfig:
        return self._node_types.get(node_type, NodeConfig())

    async def _get_or_create_manager_stack(self, market_config: MarketConfig) -> ManagerStack:
        manager_stack_key = self._get_manager_stack_key(market_config)

        manager_stack = self._manager_stacks.get(manager_stack_key)

        if not manager_stack:
            self._manager_stacks[manager_stack_key] = manager_stack = await ManagerStack.create(
                self._golem_node,
                self.payment_manager.get_allocation,
                market_config,
            )

            await manager_stack.start()

        return manager_stack

    def _get_manager_stack_key(self, market_config: MarketConfig) -> str:
        return hashlib.md5(market_config.json().encode()).hexdigest()

    def get_or_create_budget(self, budget_type: str, node_type: str, node_id: str) -> Budget:
        budget_key = self._get_budget_key(budget_type, node_type, node_id)

        budget = self._budgets.get(budget_key)

        if not budget:
            budget_class, args, kwargs = self._budget_types[budget_type].budget.import_object()

            self._budgets[budget_key] = budget = budget_class(*args, **kwargs)

        return budget

    def _get_budget_key(self, budget_type: str, node_type: str, node_id: str) -> str:
        scope = self._budget_types[budget_type].scope

        if scope is BudgetScope.CLUSTER:
            return budget_type
        elif scope is BudgetScope.NODE_TYPE:
            return f"{budget_type}-{node_type}"
        else:
            return f"{budget_type}-{node_type}-{node_id}"

    def create_node(self, node_config: NodeConfig) -> Node:
        node_id = self._get_new_node_id()

        self._nodes[node_id] = node = Node(
            node_id=node_id,
            network=self.network,
            node_config=node_config,
            get_manager_stack=self._get_or_create_manager_stack,
        )

        node.schedule_provision()

        return node

    async def delete_node(self, node: Node) -> None:
        # TODO: use schedule stop and remove instead of inline waiting
        await node.stop()

        del self._nodes[node.node_id]
