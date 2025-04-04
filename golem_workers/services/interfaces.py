from abc import ABC, abstractmethod
from typing import List, Optional

from golem_workers.services.types import (
    CreateClusterRequest,
    CreateNodeRequest,
    GetProposalsRequest,
    GetProposalsResponse,
    CreateClusterResponse,
    GetClusterResponse,
    DeleteClusterResponse,
    CreateNodeResponse,
    GetNodeResponse,
    DeleteNodeResponse,
    PortAllocationConfig,
    PortAllocationOut,
    PortReleaseResult,
    ClusterPortReleaseResult,
    AllocationStatus,
    PortStatistics,
)


class IProposalService(ABC):
    """Interface for proposal-related operations."""

    @abstractmethod
    async def get_proposals(self, request_data: GetProposalsRequest) -> GetProposalsResponse:
        """Get proposals based on request parameters."""
        pass


class IClusterService(ABC):
    """Interface for cluster management operations."""

    @abstractmethod
    async def create_cluster(self, request_data: CreateClusterRequest) -> CreateClusterResponse:
        """Create a new cluster."""
        pass

    @abstractmethod
    async def list_clusters(self) -> List[str]:
        """List all available clusters."""
        pass

    @abstractmethod
    async def get_cluster(self, cluster_id: str) -> GetClusterResponse:
        """Get details for a specific cluster."""
        pass

    @abstractmethod
    async def delete_cluster(self, cluster_id: str) -> DeleteClusterResponse:
        """Delete a cluster."""
        pass


class INodeService(ABC):
    """Interface for node management operations."""

    @abstractmethod
    async def create_node(self, request_data: CreateNodeRequest) -> CreateNodeResponse:
        """Create a new node in a cluster."""
        pass

    @abstractmethod
    async def get_node(self, cluster_id: str, node_id: str) -> GetNodeResponse:
        """Get details for a specific node."""
        pass

    @abstractmethod
    async def delete_node(self, cluster_id: str, node_id: str) -> DeleteNodeResponse:
        """Delete a node from a cluster."""
        pass


class IPortAllocationService(ABC):
    """Interface for port allocation operations."""

    @abstractmethod
    def get_config(self) -> PortAllocationConfig:
        """Get the current port allocation configuration."""
        pass

    @abstractmethod
    def allocate_port(self) -> PortAllocationOut:
        """Allocate a random available port."""
        pass

    @abstractmethod
    def use_port(self, allocation_id: str, cluster_id: str, node_id: str) -> PortAllocationOut:
        """Mark a port as in use by a specific cluster and node."""
        pass

    @abstractmethod
    def cancel_allocation(self, allocation_id: str) -> PortReleaseResult:
        """Cancel an allocation and release the port."""
        pass

    @abstractmethod
    def release_ports_by_cluster_node(
        self, cluster_id: str, node_id: Optional[str] = None
    ) -> ClusterPortReleaseResult:
        """Release all ports associated with a cluster or node."""
        pass

    @abstractmethod
    def get_allocation(self, allocation_id: str) -> PortAllocationOut:
        """Get details for a specific allocation."""
        pass

    @abstractmethod
    def list_allocations(
        self,
        status: Optional[AllocationStatus] = None,
        cluster_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[PortAllocationOut]:
        """List allocations with optional filtering."""
        pass

    @abstractmethod
    def get_statistics(self) -> "PortStatistics":
        """Get statistics about port allocations."""
        pass
