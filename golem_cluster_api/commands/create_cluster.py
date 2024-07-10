import asyncio

from pydantic import Field
from typing import Mapping, MutableMapping

from golem.node import GolemNode
from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands.base import Command, CommandResponse, CommandRequest
from golem_cluster_api.exceptions import ObjectAlreadyExists
from golem_cluster_api.models import PaymentConfig, NodeConfig, ClusterOut, BudgetConfig

# cluster robi pustą? alokacje przez payment managera
# budget control dosypuje do alokacji
# budget control musi miec mozliwosc zapisywania swoich informacji (pamiętać kiedy ostatnio dosypał do alokacji)
# budget control pozwala lub nie pozwala na stworzenie activity
# budget control jest filtrem / sorterem do noda

budget_types = {
    "__all__": [],
    "default": [
        "some.field.to.fund-testnet",
        {
            "some.field.to.initial-budget": {
                "initial_budget": 5,
            }
        },
        {
            "some.field.to.total-budget": {
                "total_budget": 5,
            }
        },
        {
            "some.field.to.per-hour-budget": {
                "budget": 1,
                "calculate_for": "node",  # enum: "node" / "node_type" / "cluster"
                "pricing": {
                    "some.pricing.function.path": {
                        "foo": "bar",
                    }
                },
            }
        },
    ],
}


class CreateClusterRequest(CommandRequest):
    cluster_id: str = "default"
    payment_config: PaymentConfig = Field(default_factory=PaymentConfig)
    budget_types: Mapping[str, BudgetConfig] = Field(default_factory=dict)
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
                payment_config=request.payment_config,
                node_types=request.node_types,
            )

            cluster.schedule_start()

            return CreateClusterResponse(
                cluster=ClusterOut.from_cluster(cluster),
            )
