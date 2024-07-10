import logging

from pydantic import Field
from typing import Mapping, Optional

from golem.node import GolemNode
from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands.base import CommandResponse, CommandRequest, Command
from golem_cluster_api.exceptions import ObjectNotFound
from golem_cluster_api.models import NodeConfig, NodeOut


# Tworzenie noda zwraca od razu i startuje jego odpalenie
# node próbuje zestawić activity ze swojego demanda, póki mu się nie uda
# uwspólnianie takich samych demandów / jednoczesne robienie wielu nodów z jednego demanda
# usuwanie demanda jesli przez 5 minut nie bedzie zadnego zainteresowania


logger = logging.getLogger(__name__)


class CreateNodeRequest(CommandRequest):
    cluster_id: str = "default"
    budget_type: str = "default"
    node_type: Optional[str] = "default"
    node_config: NodeConfig = Field(default_factory=NodeConfig)


class CreateNodeResponse(CommandResponse):
    node: NodeOut


class CreateNodeCommand(Command[CreateNodeRequest, CreateNodeResponse]):
    """Creates node. Apply logic from cluster configuration."""

    def __init__(
        self,
        golem_node: GolemNode,
        clusters: Mapping[str, Cluster],
    ) -> None:
        self._golem_node = golem_node

        self._clusters = clusters

    async def __call__(self, request: CreateNodeRequest) -> CreateNodeResponse:
        """
        Raises:
            ObjectNotFound: If given `cluster_id` is not found in cluster collection.
        """

        cluster = self._clusters.get(request.cluster_id)

        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{request.cluster_id}` does not exists!")

        cluster_node_config = cluster.get_node_type_config(request.node_type)
        node_config = cluster_node_config.combine(request.node_config)

        # TODO: Validate node config

        # TODO: Use ClusterRepository for creation scheduling
        node = cluster.create_node(node_config)

        return CreateNodeResponse(
            node=NodeOut.from_node(node),
        )
