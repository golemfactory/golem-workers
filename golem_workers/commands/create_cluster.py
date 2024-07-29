import asyncio

from pydantic import Field
from typing import Mapping, MutableMapping
from typing_extensions import Annotated

from golem.node import GolemNode
from golem_workers.cluster import Cluster
from golem_workers.commands.base import Command, CommandResponse, CommandRequest
from golem_workers.exceptions import ObjectAlreadyExists
from golem_workers.models import PaymentConfig, NodeConfig, ClusterOut, BudgetConfig


class CreateClusterRequest(CommandRequest):
    cluster_id: str = "default"
    payment_config: PaymentConfig = Field(default_factory=PaymentConfig)
    # TODO: network_types: Mapping[str, NetworkConfig]
    budget_types: Annotated[Mapping[str, BudgetConfig], Field(min_length=1)]
    node_types: Mapping[str, NodeConfig] = Field(
        default_factory=dict
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

            network = await self._golem_node.create_network(
                "192.168.0.1/16"
            )  # TODO MVP: allow for unique network for each cluster
            await self._golem_node.add_to_network(network)

            # TODO: Use ClusterRepository for creation scheduling
            self._clusters[request.cluster_id] = cluster = Cluster(
                golem_node=self._golem_node,
                cluster_id=request.cluster_id,
                network=network,
                budget_types=request.budget_types,
                payment_config=request.payment_config,
                node_types=request.node_types,
            )

            cluster.schedule_start()

            return CreateClusterResponse(
                cluster=ClusterOut.from_cluster(cluster),
            )