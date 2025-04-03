from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from golem_workers.models import (
    ProposalOut,
    ClusterOut,
    NodeOut,
)


class IProposalService(ABC):
    """Interface for proposal-related operations."""

    @abstractmethod
    async def get_proposals(self, request_data) -> List[ProposalOut]:
        """Get proposals based on request parameters."""
        pass


class IClusterService(ABC):
    """Interface for cluster management operations."""

    @abstractmethod
    async def create_cluster(self, request_data) -> ClusterOut:
        """Create a new cluster."""
        pass

    @abstractmethod
    async def list_clusters(self) -> List[str]:
        """List all available clusters."""
        pass

    @abstractmethod
    async def get_cluster(self, cluster_id: str) -> ClusterOut:
        """Get details for a specific cluster."""
        pass

    @abstractmethod
    async def delete_cluster(self, cluster_id: str) -> Dict[str, Any]:
        """Delete a cluster."""
        pass


class INodeService(ABC):
    """Interface for node management operations."""

    @abstractmethod
    async def create_node(self, request_data) -> NodeOut:
        """Create a new node in a cluster."""
        pass

    @abstractmethod
    async def get_node(self, cluster_id: str, node_id: str) -> NodeOut:
        """Get details for a specific node."""
        pass

    @abstractmethod
    async def delete_node(self, cluster_id: str, node_id: str) -> Dict[str, Any]:
        """Delete a node from a cluster."""
        pass


class IPortAllocationService(ABC):
    """Interface for port allocation operations."""

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Get the current port allocation configuration."""
        pass

    @abstractmethod
    def allocate_port(self) -> Dict[str, Any]:
        """Allocate a random available port."""
        pass

    @abstractmethod
    def use_port(self, allocation_id: str, cluster_id: str, node_id: str) -> Dict[str, Any]:
        """Mark a port as in use by a specific cluster and node."""
        pass

    @abstractmethod
    def cancel_allocation(self, allocation_id: str) -> Dict[str, Any]:
        """Cancel an allocation and release the port."""
        pass

    @abstractmethod
    def release_ports_by_cluster_node(
        self, cluster_id: str, node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Release all ports associated with a cluster or node."""
        pass

    @abstractmethod
    def get_allocation(self, allocation_id: str) -> Dict[str, Any]:
        """Get details for a specific allocation."""
        pass

    @abstractmethod
    def list_allocations(
        self,
        status: Optional[str] = None,
        cluster_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List allocations with optional filtering."""
        pass
