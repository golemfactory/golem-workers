import asyncio

from pydantic import Field
from typing import Mapping, MutableMapping, Optional

from golem.node import GolemNode
from golem_workers.cluster import Cluster
from golem_workers.commands.base import Command, CommandResponse, CommandRequest
from golem_workers.exceptions import ObjectAlreadyExists
from golem_workers.models import (
    PaymentConfig,
    NodeConfig,
    ClusterOut,
    BudgetConfig,
    NetworkConfig,
    AllocationConfig,
)


class CreateClusterRequest(CommandRequest):
    cluster_id: str = "default"
    payment_config: PaymentConfig = Field(
        default_factory=PaymentConfig,
        description="Payment configuration that will be applied on the whole cluster. Can be replaced by `payment_config` in `budget_types`.",
    )
    allocation_config: Optional[AllocationConfig] = Field(
        default=None,
        description="Allocation configuration that will be applied on the whole cluster. Can be replaced by `allocation_config` in `budget_types`.",
    )
    budget_types: Mapping[str, BudgetConfig] = Field(
        min_length=1,
        description="Collection of Budget configurations that nodes can reference by the key.",
    )
    network_types: Mapping[str, NetworkConfig] = Field(
        default_factory=dict,
        description="Collection of Network configurations that nodes can reference by the key.",
    )
    node_types: Mapping[str, NodeConfig] = Field(
        default_factory=dict,
        description="Collection of Node configurations that nodes can reference by the key. Can be extended by the node.",
    )  # TODO: Add __all__ special type support


class CreateClusterResponse(CommandResponse):
    cluster: ClusterOut


class CreateClusterCommand(Command[CreateClusterRequest, CreateClusterResponse]):
    """Creates cluster and schedules its start."""

    def __init__(
        self,
        golem_node: GolemNode,
        clusters_lock: asyncio.Lock,
        clusters: MutableMapping[str, Cluster],
    ) -> None:
        self._golem_node = golem_node
        self._clusters_lock = clusters_lock
        self._clusters = clusters

    async def __call__(self, request: CreateClusterRequest) -> CreateClusterResponse:
        """
        Raises:
            ObjectAlreadyExists: If given `cluster_id` already exists in cluster collection.
        """
        async with self._clusters_lock:
            if request.cluster_id in self._clusters:
                raise ObjectAlreadyExists(f"Cluster with id `{request.cluster_id}` already exists!")

            # TODO: Use ClusterRepository for creation scheduling
            self._clusters[request.cluster_id] = cluster = Cluster(
                golem_node=self._golem_node,
                cluster_id=request.cluster_id,
                budget_types=request.budget_types,
                payment_config=request.payment_config,
                allocation_config=request.allocation_config,
                network_types=request.network_types,
                node_types=request.node_types,
            )

            cluster.schedule_start()

            return CreateClusterResponse(
                cluster=ClusterOut.from_cluster(cluster),
            )
