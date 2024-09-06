import asyncio
import hashlib
import logging
from typing import Dict, Mapping, Optional

from golem.node import GolemNode
from golem.resources import Network, Allocation
from golem.utils.asyncio import create_task_with_logging
from golem.utils.logging import get_trace_id_name
from golem_workers.budgets import Budget
from golem_workers.cluster.manager_stack import ManagerStack

from golem_workers.cluster.node import Node
from golem_workers.golem import DriverListAllocationPaymentManager
from golem_workers.models import (
    NodeConfig,
    PaymentConfig,
    BudgetConfig,
    BudgetScope,
    ClusterState,
    MarketConfig,
    NetworkConfig,
    NodeNetworkConfig,
    AllocationConfig,
)

logger = logging.getLogger(__name__)


class Cluster:
    """Top-level element that is responsible for maintaining all components for single cluster."""

    def __init__(
        self,
        golem_node: GolemNode,
        cluster_id: str,
        budget_types: Mapping[str, BudgetConfig],  # TODO: make budget optional
        payment_config: Optional[PaymentConfig] = None,
        allocation_config: Optional[AllocationConfig] = None,
        network_types: Optional[Mapping[str, NetworkConfig]] = None,
        node_types: Optional[Mapping[str, NodeConfig]] = None,
    ) -> None:
        self._golem_node = golem_node
        self._cluster_id = cluster_id
        self._budget_types = budget_types

        self._payment_config = payment_config or PaymentConfig()
        self._allocation_config = allocation_config
        self._network_types = network_types or {}
        self._node_types = node_types or {}

        self._allocation: Optional[Allocation] = None
        self._manager_stacks: Dict[str, ManagerStack] = {}
        self._budgets: Dict[str, Budget] = {}
        self._networks: Dict[str, Network] = {}
        self._nodes: Dict[str, Node] = {}
        self._nodes_id_counter = 0
        self._start_task: Optional[asyncio.Task] = None

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
        """Read-only map of named nodes."""

        return self._nodes

    @property
    def budget_types(self) -> Mapping[str, BudgetConfig]:
        """Read-only map of named budget configurations."""

        return self._budget_types

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

        if self._allocation_config:
            self._allocation = await self._get_or_create_allocation(
                self._allocation_config, self._payment_config
            )

        for network_name, network_config in self._network_types.items():
            self._networks[network_name] = await self._golem_node.create_network(
                ip=network_config.ip,
                mask=network_config.mask,
                gateway=network_config.gateway,
                add_requestor=network_config.add_requestor,
                requestor_ip=network_config.requestor_ip,
            )

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

        if (
            self._allocation_config
            and not self._allocation_config.is_external_allocation()
            and self._allocation
        ):
            await self._allocation.release()

        self._allocation = None

        await asyncio.gather(*[network.remove() for network in self._networks.values()])

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

    def get_node_type_config(self, node_type: str) -> Optional[NodeConfig]:
        return self._node_types.get(node_type)

    def _get_network(self, network_name: str) -> Network:
        return self._networks[network_name]

    async def _get_or_create_allocation(
        self, allocation_config: AllocationConfig, payment_config: PaymentConfig
    ) -> Optional[Allocation]:
        if allocation_config.id:
            api = Allocation._get_api(self._golem_node)
            try:
                data = await api.get_allocation(allocation_config.id)
            except ValueError:
                raise RuntimeError(f"Allocation with id `{allocation_config.id}` does not exists!")
            else:
                return Allocation(self._golem_node, data.allocation_id, data)
        else:
            payment_manager = DriverListAllocationPaymentManager(
                self._golem_node,
                budget=float(allocation_config.amount),
                network=payment_config.network,
                driver=payment_config.driver,
            )

            return await payment_manager.get_allocation()

    async def _get_or_create_manager_stack(
        self, market_config: MarketConfig, budget_key: str
    ) -> ManagerStack:
        # TODO: Lock
        manager_stack_key = self._get_manager_stack_key(market_config, budget_key)

        manager_stack = self._manager_stacks.get(manager_stack_key)

        if not manager_stack:
            self._manager_stacks[manager_stack_key] = (
                manager_stack
            ) = await ManagerStack.create_agreement_stack(
                self._golem_node,
                market_config,
                self._budgets[budget_key],
            )

            await manager_stack.start()

        return manager_stack

    def _get_manager_stack_key(self, market_config: MarketConfig, budget_key: str) -> str:
        hashed_stack = hashlib.md5(market_config.json().encode()).hexdigest()
        return f"{hashed_stack}-{budget_key}"

    async def _get_or_create_budget(self, budget_type: str, budget_key: str) -> Budget:
        # TODO: lock
        budget = self._budgets.get(budget_key)

        if not budget:
            budget_type = self._budget_types[budget_type]
            budget_class, args, kwargs = budget_type.budget.import_object()

            if budget_type.allocation_config:  # Budget allocation config takes precedence
                allocation = await self._get_or_create_allocation(
                    budget_type.allocation_config,
                    budget_type.payment_config or self._payment_config,
                )
                allow_allocation_amendment = False
            elif self._allocation:  # Use cluster global allocation
                allocation = self._allocation
                allow_allocation_amendment = False
            else:  # create budget exclusive allocation
                allocation = await self._get_or_create_allocation(
                    AllocationConfig(amount=0), budget_type.payment_config or self._payment_config
                )
                allow_allocation_amendment = True

            self._budgets[budget_key] = budget = budget_class(
                allocation, allow_allocation_amendment, *args, **kwargs
            )

            await budget.start()

        return budget

    def _get_budget_key(self, budget_type: str, node_type: str, node_id: str) -> str:
        scope = self._budget_types[budget_type].scope

        if scope is BudgetScope.CLUSTER:
            return f"{budget_type}-cluster"
        elif scope is BudgetScope.NODE_TYPE:
            return f"{budget_type}-node_type-{node_type}"
        else:
            return f"{budget_type}-node_id-{node_id}"

    async def create_node(
        self,
        node_config: NodeConfig,
        node_type: str,
        budget_type: str,
        node_networks: Mapping[str, NodeNetworkConfig],
    ) -> Node:
        node_id = self._get_new_node_id()

        budget_key = self._get_budget_key(budget_type, node_type, node_id)
        budget = await self._get_or_create_budget(budget_type, budget_key)

        manager_stack = await self._get_or_create_manager_stack(
            node_config.market_config, budget_key
        )

        networks = {
            network_name: self._networks[network_name] for network_name in node_networks.keys()
        }

        self._nodes[node_id] = node = Node(
            golem_node=self._golem_node,
            node_id=node_id,
            networks_config=node_networks,
            node_config=node_config,
            budget=budget,
            manager_stack=manager_stack,
            networks=networks,
        )

        node.schedule_provision()

        return node

    async def delete_node(self, node: Node) -> None:
        # TODO: use schedule stop and remove instead of inline waiting
        await node.stop()

        del self._nodes[node.node_id]
