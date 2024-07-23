from typing import Mapping

from golem_workers.cluster import Cluster
from golem_workers.commands.base import Command, CommandRequest, CommandResponse
from golem_workers.exceptions import ObjectNotFound
from golem_workers.models import NodeOut


class GetNodeRequest(CommandRequest):
    cluster_id: str
    node_id: str


class GetNodeResponse(CommandResponse):
    node: NodeOut


class GetNodeCommand(Command[GetNodeRequest, GetNodeResponse]):
    """Read node info and status"""

    def __init__(self, clusters: Mapping[str, Cluster]) -> None:
        self._clusters = clusters

    async def __call__(self, request: GetNodeRequest) -> GetNodeResponse:
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

        return GetNodeResponse(
            node=NodeOut.from_node(node),
        )
