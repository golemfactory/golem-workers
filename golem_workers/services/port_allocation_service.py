from typing import List, Optional

from golem_workers.services.interfaces import IPortAllocationService
from golem_workers.services.port_allocation import AllocationManager
from golem_workers.services.types import (
    PortAllocationConfig,
    PortAllocationOut,
    PortReleaseResult,
    ClusterPortReleaseResult,
    AllocationStatus,
    PortStatistics,
)


class PortAllocationService(IPortAllocationService):
    """Service for managing port allocations."""

    def __init__(self, allocation_manager: AllocationManager):
        self._manager = allocation_manager

    def get_config(self) -> PortAllocationConfig:
        """Get the current port allocation configuration."""
        config_dict = self._manager.get_config()
        return PortAllocationConfig(**config_dict)

    def allocate_port(self) -> PortAllocationOut:
        """Allocate a random available port."""
        allocation_dict = self._manager.allocate_port()
        return PortAllocationOut(**allocation_dict)

    def use_port(self, allocation_id: str, cluster_id: str, node_id: str) -> PortAllocationOut:
        """Mark a port as in use by a specific cluster and node."""
        allocation_dict = self._manager.use_port(allocation_id, cluster_id, node_id)
        return PortAllocationOut(**allocation_dict)

    def cancel_allocation(self, allocation_id: str) -> PortReleaseResult:
        """Cancel an allocation and release the port."""
        release_dict = self._manager.cancel_allocation(allocation_id)
        return PortReleaseResult(**release_dict)

    def release_ports_by_cluster_node(
        self, cluster_id: str, node_id: Optional[str] = None
    ) -> ClusterPortReleaseResult:
        """Release all ports associated with a cluster or node."""
        release_dict = self._manager.release_ports_by_cluster_node(cluster_id, node_id)
        return ClusterPortReleaseResult(**release_dict)

    def get_allocation(self, allocation_id: str) -> PortAllocationOut:
        """Get details for a specific allocation."""
        allocation_dict = self._manager.get_allocation(allocation_id)
        return PortAllocationOut(**allocation_dict)

    def list_allocations(
        self,
        status: Optional[AllocationStatus] = None,
        cluster_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[PortAllocationOut]:
        """List allocations with optional filtering."""
        status_str = status.value if status else None
        allocation_dicts = self._manager.list_allocations(status_str, cluster_id, node_id)
        return [PortAllocationOut(**allocation_dict) for allocation_dict in allocation_dicts]

    def get_statistics(self) -> PortStatistics:
        """Get statistics about port allocations."""
        stats_dict = self._manager.get_statistics()
        return PortStatistics(**stats_dict)
