import logging

from pydantic import model_validator
from typing import Mapping, Optional

from golem.node import GolemNode
from golem_workers.cluster import Cluster
from golem_workers.commands.base import CommandResponse, CommandRequest, Command
from golem_workers.exceptions import ObjectNotFound
from golem_workers.models import NodeConfig, NodeOut, BudgetScope


logger = logging.getLogger(__name__)


class CreateNodeRequest(CommandRequest):
    cluster_id: str = "default"
    budget_type: str = "default"
    node_type: Optional[str] = "default"
    node_config: Optional[NodeConfig] = None

    @model_validator(mode="after")
    def validate_node_type_and_node_config(self):
        if self.node_type is None and self.node_config is None:
            raise ValueError("At least one of `node_type` or `node_config` must be defined!")

        return self


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

        node_config = request.node_config

        if request.node_type is not None:
            cluster_node_config = cluster.get_node_type_config(request.node_type)

            if not cluster_node_config:
                raise ObjectNotFound(
                    f"Node type `{request.budget_type}` does not exists in the cluster!"
                )

            if node_config is not None:
                node_config = cluster_node_config.combine(node_config)

        budget_config = cluster.budget_types.get(request.budget_type)

        if budget_config is None:
            raise ObjectNotFound(
                f"Budget type `{request.budget_type}` does not exists in the cluster!"
            )

        if budget_config.scope == BudgetScope.NODE_TYPE and request.node_type is None:
            raise ValueError(
                f"Budget type `{request.budget_type}` with scope of `{BudgetScope.NODE_TYPE}` requires `node_type` field!"
            )

        # TODO: Validate node config

        # TODO: Use ClusterRepository for creation scheduling
        node = cluster.create_node(node_config, request.node_type, request.budget_type)

        return CreateNodeResponse(
            node=NodeOut.from_node(node),
        )
