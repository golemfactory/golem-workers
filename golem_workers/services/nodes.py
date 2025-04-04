import logging
from typing import Mapping, Optional

from golem.node import GolemNode

from golem_workers.cluster import Cluster
from golem_workers.exceptions import ObjectNotFound
from golem_workers.models import BudgetScope, NodeOut, NodeConfig
from golem_workers.cluster.node import Node
from golem_workers.services.interfaces import INodeService
from golem_workers.services.types import (
    CreateNodeRequest,
    CreateNodeResponse,
    GetNodeResponse,
    DeleteNodeResponse,
)

logger = logging.getLogger(__name__)


class NodeService(INodeService):
    """Service for managing nodes within clusters."""

    def __init__(
        self,
        golem_node: GolemNode,
        clusters: Mapping[str, Cluster],
        port_allocation_service=None,
    ):
        self._golem_node = golem_node
        self._clusters = clusters
        self._port_allocation_service = port_allocation_service

    def _get_cluster(self, cluster_id: str) -> Cluster:
        """Get cluster by ID or raise ObjectNotFound."""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{cluster_id}` does not exists!")
        return cluster

    def _get_node(self, cluster: Cluster, node_id: str) -> Node:
        """Get node from cluster or raise ObjectNotFound."""
        node = cluster.nodes.get(node_id)
        if not node:
            raise ObjectNotFound(f"Node with id `{node_id}` does not exists in cluster!")
        return node

    def _prepare_node_config(
        self, cluster: Cluster, node_type: Optional[str], node_config: Optional[NodeConfig]
    ) -> Optional[NodeConfig]:
        """Prepare node configuration combining type and specific config."""
        if node_type is None:
            return node_config

        cluster_node_config = cluster.get_node_type_config(node_type)
        if not cluster_node_config:
            raise ObjectNotFound(f"Node type `{node_type}` does not exists in the cluster!")

        if node_config is not None:
            return cluster_node_config.combine(node_config)
        return cluster_node_config

    def _validate_budget_config(
        self, cluster: Cluster, budget_type: str, node_type: Optional[str]
    ) -> None:
        """Validate budget configuration."""
        budget_config = cluster.budget_types.get(budget_type)

        if budget_config is None:
            raise ObjectNotFound(f"Budget type `{budget_type}` does not exists in the cluster!")

        if budget_config.scope == BudgetScope.NODE_TYPE and node_type is None:
            raise ValueError(
                f"Budget type `{budget_type}` with scope of `{BudgetScope.NODE_TYPE}` requires `node_type` field!"
            )

    async def create_node(self, request_data: CreateNodeRequest) -> CreateNodeResponse:
        """Create a new node in a cluster."""
        # Get and validate cluster
        cluster = self._get_cluster(request_data.cluster_id)

        # Process node configuration
        node_config = self._prepare_node_config(
            cluster, request_data.node_type, request_data.node_config
        )

        # Validate budget configuration
        self._validate_budget_config(cluster, request_data.budget_type, request_data.node_type)

        # Create node
        node = await cluster.create_node(
            node_config,
            request_data.node_type,
            request_data.budget_type,
            request_data.node_networks,
            labels=request_data.labels,
        )

        return CreateNodeResponse(node=NodeOut.from_node(node))

    async def get_node(self, cluster_id: str, node_id: str) -> GetNodeResponse:
        """Get details for a specific node."""
        cluster = self._get_cluster(cluster_id)
        node = self._get_node(cluster, node_id)
        return GetNodeResponse(node=NodeOut.from_node(node))

    async def delete_node(self, cluster_id: str, node_id: str) -> DeleteNodeResponse:
        """Delete a node from a cluster."""
        cluster = self._get_cluster(cluster_id)
        node = self._get_node(cluster, node_id)

        # Delete node
        await cluster.delete_node(node)

        # Release any ports associated with this node after deleting it
        if self._port_allocation_service:
            self._port_allocation_service.release_ports_by_cluster_node(cluster_id, node_id)

        return DeleteNodeResponse(node=NodeOut.from_node(node))
