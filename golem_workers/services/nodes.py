import logging
from typing import Dict, Mapping, Any, Optional

from golem.node import GolemNode

from golem_workers.cluster import Cluster
from golem_workers.exceptions import ObjectNotFound, ValueError
from golem_workers.models import BudgetScope, NodeOut
from golem_workers.services.interfaces import INodeService

logger = logging.getLogger(__name__)


class NodeService(INodeService):
    """Service for managing nodes within clusters."""
    
    def __init__(
        self,
        golem_node: GolemNode,
        clusters: Mapping[str, Cluster],
    ):
        self._golem_node = golem_node
        self._clusters = clusters
    
    async def create_node(self, request_data) -> NodeOut:
        """Create a new node in a cluster."""
        cluster = self._clusters.get(request_data.cluster_id)
        
        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{request_data.cluster_id}` does not exists!")
        
        node_config = request_data.node_config
        
        if request_data.node_type is not None:
            cluster_node_config = cluster.get_node_type_config(request_data.node_type)
            
            if not cluster_node_config:
                raise ObjectNotFound(
                    f"Node type `{request_data.budget_type}` does not exists in the cluster!"
                )
            
            if node_config is not None:
                node_config = cluster_node_config.combine(node_config)
        
        budget_config = cluster.budget_types.get(request_data.budget_type)
        
        if budget_config is None:
            raise ObjectNotFound(
                f"Budget type `{request_data.budget_type}` does not exists in the cluster!"
            )
        
        if budget_config.scope == BudgetScope.NODE_TYPE and request_data.node_type is None:
            raise ValueError(
                f"Budget type `{request_data.budget_type}` with scope of `{BudgetScope.NODE_TYPE}` requires `node_type` field!"
            )
        
        # Create node
        node = await cluster.create_node(
            node_config,
            request_data.node_type,
            request_data.budget_type,
            request_data.node_networks,
            labels=request_data.labels,
        )
        
        return NodeOut.from_node(node)
    
    async def get_node(self, cluster_id: str, node_id: str) -> NodeOut:
        """Get details for a specific node."""
        cluster = self._clusters.get(cluster_id)
        
        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{cluster_id}` does not exists!")
        
        node = cluster.nodes.get(node_id)
        
        if not node:
            raise ObjectNotFound(f"Node with id `{node_id}` does not exists in cluster!")
        
        return NodeOut.from_node(node)
    
    async def delete_node(self, cluster_id: str, node_id: str) -> Dict[str, Any]:
        """Delete a node from a cluster."""
        cluster = self._clusters.get(cluster_id)
        
        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{cluster_id}` does not exists!")
        
        node = cluster.nodes.get(node_id)
        
        if not node:
            raise ObjectNotFound(f"Node with id `{node_id}` does not exists in cluster!")
        
        # Delete node
        await cluster.delete_node(node)
        
        return {"node": NodeOut.from_node(node)}