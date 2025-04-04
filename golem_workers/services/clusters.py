import asyncio
from typing import List, MutableMapping

from golem.node import GolemNode

from golem_workers.cluster import Cluster
from golem_workers.exceptions import ObjectAlreadyExists, ObjectNotFound
from golem_workers.models import (
    ClusterOut,
)
from golem_workers.services.interfaces import IClusterService
from golem_workers.services.types import (
    CreateClusterRequest,
    CreateClusterResponse,
    GetClusterResponse,
    DeleteClusterResponse,
)


class ClusterService(IClusterService):
    """Service for managing clusters."""

    def __init__(
        self,
        golem_node: GolemNode,
        clusters_lock: asyncio.Lock,
        clusters: MutableMapping[str, Cluster],
        port_allocation_service=None,
    ):
        self._golem_node = golem_node
        self._clusters_lock = clusters_lock
        self._clusters = clusters
        self._port_allocation_service = port_allocation_service

    async def create_cluster(self, request_data: CreateClusterRequest) -> CreateClusterResponse:
        """Create a new cluster."""
        async with self._clusters_lock:
            cluster_id = request_data.cluster_id

            if cluster_id in self._clusters:
                raise ObjectAlreadyExists(f"Cluster with id `{cluster_id}` already exists!")

            # Create cluster
            self._clusters[cluster_id] = cluster = Cluster(
                golem_node=self._golem_node,
                cluster_id=cluster_id,
                budget_types=request_data.budget_types,
                payment_config=request_data.payment_config,
                allocation_config=request_data.allocation_config,
                network_types=request_data.network_types,
                node_types=request_data.node_types,
                labels=request_data.labels,
            )

            cluster.schedule_start()

            return CreateClusterResponse(cluster=ClusterOut.from_cluster(cluster))

    async def list_clusters(self) -> List[str]:
        """List all available clusters."""
        async with self._clusters_lock:
            return list(self._clusters.keys())

    async def get_cluster(self, cluster_id: str) -> GetClusterResponse:
        """Get details for a specific cluster."""
        cluster = self._clusters.get(cluster_id)

        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{cluster_id}` does not exists!")

        return GetClusterResponse(cluster=ClusterOut.from_cluster(cluster))

    async def delete_cluster(self, cluster_id: str) -> DeleteClusterResponse:
        """Delete a cluster."""
        async with self._clusters_lock:
            cluster = self._clusters.get(cluster_id)

            if not cluster:
                raise ObjectNotFound(f"Cluster with id `{cluster_id}` does not exists!")

            # Stop and remove cluster
            await cluster.stop()
            del self._clusters[cluster_id]

            # Release any ports associated with this cluster after deleting it
            if self._port_allocation_service:
                self._port_allocation_service.release_ports_by_cluster_node(cluster_id)

            return DeleteClusterResponse(cluster=ClusterOut.from_cluster(cluster))
