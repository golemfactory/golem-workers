from typing import Mapping

from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands.base import Command, CommandRequest, CommandResponse
from golem_cluster_api.exceptions import ObjectNotFound
from golem_cluster_api.models import NodeOut


class DeleteNodeRequest(CommandRequest):
    cluster_id: str
    node_id: str


class DeleteNodeResponse(CommandResponse):
    node: NodeOut


class DeleteNodeCommand(Command[DeleteNodeRequest, DeleteNodeResponse]):
    """Marks node for deletion and schedules its stop."""

    def __init__(self, clusters: Mapping[str, Cluster]) -> None:
        self._clusters = clusters

    async def __call__(self, request: DeleteNodeRequest) -> DeleteNodeResponse:
        """
        Raises:
            ObjectNotFound: If given `cluster_id` is not found in cluster collection or given
                `node_id` is not found in existing cluster.
        """

        cluster = self._clusters.get(request.cluster_id)

        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{request.cluster_id}` does not exists!")

        node = cluster.nodes.get(request.node_id)

        if not node:
            raise ObjectNotFound(f"Node with id `{request.node_id}` does not exists in cluster!")

        # TODO: Use ClusterRepository for deletion scheduling
        await cluster.delete_node(node)

        return DeleteNodeResponse(
            node=NodeOut.from_node(node),
        )
