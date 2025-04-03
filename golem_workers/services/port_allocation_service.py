from typing import Dict, List, Optional, Any

from golem_workers.services.interfaces import IPortAllocationService
from golem_workers.services.port_allocation import AllocationManager


class PortAllocationService(IPortAllocationService):
    """Service for managing port allocations."""
    
    def __init__(self, allocation_manager: AllocationManager):
        self._manager = allocation_manager
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current port allocation configuration."""
        return self._manager.get_config()
    
    def allocate_port(self) -> Dict[str, Any]:
        """Allocate a random available port."""
        return self._manager.allocate_port()
    
    def use_port(self, allocation_id: str, cluster_id: str, node_id: str) -> Dict[str, Any]:
        """Mark a port as in use by a specific cluster and node."""
        return self._manager.use_port(allocation_id, cluster_id, node_id)
    
    def cancel_allocation(self, allocation_id: str) -> Dict[str, Any]:
        """Cancel an allocation and release the port."""
        return self._manager.cancel_allocation(allocation_id)
    
    def release_ports_by_cluster_node(self, cluster_id: str, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Release all ports associated with a cluster or node."""
        return self._manager.release_ports_by_cluster_node(cluster_id, node_id)
    
    def get_allocation(self, allocation_id: str) -> Dict[str, Any]:
        """Get details for a specific allocation."""
        return self._manager.get_allocation(allocation_id)
    
    def list_allocations(
        self,
        status: Optional[str] = None,
        cluster_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List allocations with optional filtering."""
        return self._manager.list_allocations(status, cluster_id, node_id)