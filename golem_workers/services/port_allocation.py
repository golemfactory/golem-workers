import time
import uuid
import socket
import random
import threading
from typing import Dict, Set, Optional, List, Tuple
from datetime import datetime, timedelta


class AllocationStatus:
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    RELEASED = "released"


class PortAllocation:
    def __init__(self, port: int, allocation_id: str, expires_at: datetime):
        self.port = port
        self.allocation_id = allocation_id
        self.expires_at = expires_at
        self.status = AllocationStatus.ALLOCATED
        self.cluster_id: Optional[str] = None
        self.node_id: Optional[str] = None
        self.socket: Optional[socket.socket] = None

    def to_dict(self):
        return {
            "allocation_id": self.allocation_id,
            "port": self.port,
            "status": self.status,
            "expires_at": self.expires_at.isoformat(),
            "cluster_id": self.cluster_id,
            "node_id": self.node_id,
        }


class AllocationManager:
    def __init__(self, min_port: int = 8050, max_port: int = 9999, expiration_minutes: int = 5):
        # Configuration
        self.min_port = min_port
        self.max_port = max_port
        self.expiration_minutes = expiration_minutes

        # Thread lock for synchronization
        self.lock = threading.RLock()

        # Data structures
        self.allocations: Dict[str, PortAllocation] = {}  # allocation_id -> PortAllocation
        self.port_to_allocation: Dict[int, str] = {}  # port -> allocation_id
        self.cluster_allocations: Dict[str, Set[str]] = {}  # cluster_id -> set of allocation_ids
        self.node_allocations: Dict[
            Tuple[str, str], Set[str]
        ] = {}  # (cluster_id, node_id) -> set of allocation_ids

        # Start expiration checker thread
        self.running = True
        self.expiration_thread = threading.Thread(target=self._check_expirations, daemon=True)
        self.expiration_thread.start()

    def get_config(self):
        """Get current configuration."""
        with self.lock:
            return {
                "min_port": self.min_port,
                "max_port": self.max_port,
                "expiration_minutes": self.expiration_minutes,
            }

    def update_config(
        self,
        min_port: Optional[int] = None,
        max_port: Optional[int] = None,
        expiration_minutes: Optional[int] = None,
    ):
        """Update configuration."""
        with self.lock:
            if min_port is not None:
                self.min_port = min_port
            if max_port is not None:
                self.max_port = max_port
            if expiration_minutes is not None:
                self.expiration_minutes = expiration_minutes
            return self.get_config()

    def allocate_port(self) -> Dict:
        """Allocate a random available port."""
        with self.lock:
            # Generate a set of ports to try in random order
            ports_to_try = list(range(self.min_port, self.max_port + 1))
            random.shuffle(ports_to_try)

            # Try each port until we find an available one
            for port in ports_to_try:
                if port in self.port_to_allocation:
                    continue

                # Try to bind to the port to check if it's available
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("0.0.0.0", port))

                    # Generate allocation ID and create allocation
                    allocation_id = f"alloc-{uuid.uuid4().hex[:8]}"
                    expires_at = datetime.now() + timedelta(minutes=self.expiration_minutes)

                    allocation = PortAllocation(port, allocation_id, expires_at)
                    allocation.socket = sock

                    # Store allocation
                    self.allocations[allocation_id] = allocation
                    self.port_to_allocation[port] = allocation_id

                    return allocation.to_dict()
                except OSError:
                    # Port is not available, try the next one
                    continue

            # If we get here, no ports are available
            raise RuntimeError("No available ports in the configured range")

    def use_port(self, allocation_id: str, cluster_id: str, node_id: str) -> Dict:
        """Mark a port as in use by a specific cluster and node."""
        with self.lock:
            if allocation_id not in self.allocations:
                raise KeyError(f"Allocation {allocation_id} not found")

            allocation = self.allocations[allocation_id]

            if allocation.status != AllocationStatus.ALLOCATED:
                raise ValueError(f"Allocation {allocation_id} is not in allocated state")

            # Close the socket to make the port available for use
            if allocation.socket:
                allocation.socket.close()
                allocation.socket = None

            # Update allocation information
            allocation.status = AllocationStatus.IN_USE
            allocation.cluster_id = cluster_id
            allocation.node_id = node_id

            # Add to cluster and node tracking
            if cluster_id not in self.cluster_allocations:
                self.cluster_allocations[cluster_id] = set()
            self.cluster_allocations[cluster_id].add(allocation_id)

            node_key = (cluster_id, node_id)
            if node_key not in self.node_allocations:
                self.node_allocations[node_key] = set()
            self.node_allocations[node_key].add(allocation_id)

            return allocation.to_dict()

    def cancel_allocation(self, allocation_id: str) -> Dict:
        """Cancel an allocation and release the port."""
        with self.lock:
            if allocation_id not in self.allocations:
                raise KeyError(f"Allocation {allocation_id} not found")

            return self._release_allocation(allocation_id)

    def _release_allocation(self, allocation_id: str) -> Dict:
        """Internal method to release an allocation."""
        allocation = self.allocations[allocation_id]

        # Close the socket if it exists
        if allocation.socket:
            allocation.socket.close()
            allocation.socket = None

        # Update tracking structures
        port = allocation.port
        if allocation.cluster_id:
            if allocation.cluster_id in self.cluster_allocations:
                self.cluster_allocations[allocation.cluster_id].discard(allocation_id)
                if not self.cluster_allocations[allocation.cluster_id]:
                    del self.cluster_allocations[allocation.cluster_id]

        if allocation.cluster_id and allocation.node_id:
            node_key = (allocation.cluster_id, allocation.node_id)
            if node_key in self.node_allocations:
                self.node_allocations[node_key].discard(allocation_id)
                if not self.node_allocations[node_key]:
                    del self.node_allocations[node_key]

        # Remove the allocation
        del self.allocations[allocation_id]
        if port in self.port_to_allocation:
            del self.port_to_allocation[port]

        return {"port": port, "status": AllocationStatus.RELEASED}

    def release_ports_by_cluster_node(self, cluster_id: str, node_id: Optional[str] = None) -> Dict:
        """Release all ports associated with a cluster or node."""
        with self.lock:
            released_ports = []

            # If node_id is provided, release ports for that specific node
            if node_id:
                node_key = (cluster_id, node_id)
                if node_key in self.node_allocations:
                    allocation_ids = list(self.node_allocations[node_key])
                    for allocation_id in allocation_ids:
                        allocation = self.allocations.get(allocation_id)
                        if allocation:
                            released_ports.append(allocation.port)
                            self._release_allocation(allocation_id)

            # Otherwise, release all ports for the cluster
            elif cluster_id in self.cluster_allocations:
                allocation_ids = list(self.cluster_allocations[cluster_id])
                for allocation_id in allocation_ids:
                    allocation = self.allocations.get(allocation_id)
                    if allocation:
                        released_ports.append(allocation.port)
                        self._release_allocation(allocation_id)

            return {"released_ports": released_ports, "count": len(released_ports)}

    def get_allocation(self, allocation_id: str) -> Dict:
        """Get details for a specific allocation."""
        with self.lock:
            if allocation_id not in self.allocations:
                raise KeyError(f"Allocation {allocation_id} not found")

            return self.allocations[allocation_id].to_dict()

    def list_allocations(
        self,
        status: Optional[str] = None,
        cluster_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[Dict]:
        """List allocations with optional filtering."""
        with self.lock:
            result = []

            for allocation in self.allocations.values():
                # Apply filters
                if status and allocation.status != status:
                    continue
                if cluster_id and allocation.cluster_id != cluster_id:
                    continue
                if node_id and allocation.node_id != node_id:
                    continue

                result.append(allocation.to_dict())

            return result

    def get_statistics(self) -> Dict:
        """Get statistics about current allocations."""
        with self.lock:
            allocated_count = sum(
                1 for a in self.allocations.values() if a.status == AllocationStatus.ALLOCATED
            )
            in_use_count = sum(
                1 for a in self.allocations.values() if a.status == AllocationStatus.IN_USE
            )
            total_ports = self.max_port - self.min_port + 1

            return {
                "status": "healthy",
                "total_ports": total_ports,
                "allocated_ports": allocated_count,
                "in_use_ports": in_use_count,
                "available_ports": total_ports - len(self.port_to_allocation),
            }

    def _check_expirations(self):
        """Background thread to check for expired allocations."""
        while self.running:
            # Sleep for a short period to reduce CPU usage
            time.sleep(5)

            now = datetime.now()
            expired_allocations = []

            # Find expired allocations
            with self.lock:
                for allocation_id, allocation in self.allocations.items():
                    if (
                        allocation.status == AllocationStatus.ALLOCATED
                        and allocation.expires_at <= now
                    ):
                        expired_allocations.append(allocation_id)

                # Release each expired allocation
                for allocation_id in expired_allocations:
                    self._release_allocation(allocation_id)

    def shutdown(self):
        """Stop the expiration checker thread and release all allocations."""
        self.running = False
        if self.expiration_thread.is_alive():
            self.expiration_thread.join(timeout=1)

        # Release all allocations
        with self.lock:
            allocation_ids = list(self.allocations.keys())
            for allocation_id in allocation_ids:
                self._release_allocation(allocation_id)
