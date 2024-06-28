from typing import MutableMapping

import asyncio

from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands.base import Command, CommandRequest, CommandResponse
from golem_cluster_api.exceptions import ObjectNotFound
from golem_cluster_api.models import ClusterOut


class DeleteClusterRequest(CommandRequest):
    cluster_id: str


class DeleteClusterResponse(CommandResponse):
    cluster: ClusterOut


class DeleteClusterCommand(Command[DeleteClusterRequest, DeleteClusterResponse]):
    """Marks cluster for deletion and schedules its stop."""

    def __init__(
        self,
        clusters_lock: asyncio.Lock,
        clusters: MutableMapping[str, Cluster],
    ) -> None:
        self._clusters_lock = clusters_lock
        self._clusters = clusters

    async def __call__(self, request: DeleteClusterRequest) -> DeleteClusterResponse:
        """
        Raises:
            ObjectNotFound: If given `cluster_id` is not found in cluster collection.
        """

        async with self._clusters_lock:
            cluster = self._clusters.get(request.cluster_id)

            if not cluster:
                raise ObjectNotFound(f"Cluster with id `{request.cluster_id}` does not exists!")

            # TODO: use schedule stop and remove instead of inline waiting
            # TODO: Use ClusterRepository for deletion scheduling
            await cluster.stop()

            del self._clusters[request.cluster_id]

            return DeleteClusterResponse(
                cluster=ClusterOut.from_cluster(cluster),
            )
