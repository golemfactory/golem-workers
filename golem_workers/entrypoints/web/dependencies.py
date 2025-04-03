from fastapi import Request

from golem_workers.services.interfaces import (
    IProposalService,
    IClusterService,
    INodeService,
    IPortAllocationService,
)


async def get_proposal_service(request: Request) -> IProposalService:
    """Get the proposal service from the container."""
    return await request.app.state.container.services.proposal_service()


async def get_cluster_service(request: Request) -> IClusterService:
    """Get the cluster service from the container."""
    return await request.app.state.container.services.cluster_service()


async def get_node_service(request: Request) -> INodeService:
    """Get the node service from the container."""
    return await request.app.state.container.services.node_service()


async def get_port_allocation_service(request: Request) -> IPortAllocationService:
    """Get the port allocation service from the container."""
    return await request.app.state.container.services.port_allocation_service()
