from typing import Mapping

from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands.base import Command, CommandRequest, CommandResponse
from golem_cluster_api.exceptions import ObjectNotFound
from golem_cluster_api.models import ClusterOut


class GetClusterRequest(CommandRequest):
    cluster_id: str


class GetClusterResponse(CommandResponse):
    cluster: ClusterOut


class GetClusterCommand(Command[GetClusterRequest, GetClusterResponse]):
    """Reads cluster info and status."""

    def __init__(self, clusters: Mapping[str, Cluster]) -> None:
        self._clusters = clusters

    async def __call__(self, request: GetClusterRequest) -> GetClusterResponse:
        """
        Raises:
            ObjectNotFound: If given `cluster_id` is not found in cluster collection.
        """

        cluster = self._clusters.get(request.cluster_id)

        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{request.cluster_id}` does not exists!")

        return GetClusterResponse(
            cluster=ClusterOut.from_cluster(cluster),
        )
