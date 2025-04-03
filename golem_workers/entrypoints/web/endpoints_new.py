from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from golem_workers import __version__
from golem_workers import commands
from golem_workers.commands import (
    GetClusterRequest,
    DeleteClusterRequest,
    GetNodeRequest,
    DeleteNodeRequest,
)
from golem_workers.entrypoints.web.dependencies import (
    get_proposal_service,
    get_cluster_service,
    get_node_service,
    get_port_allocation_service,
)
from golem_workers.events import event_bus
from golem_workers.services.interfaces import (
    IProposalService,
    IClusterService,
    INodeService,
    IPortAllocationService,
)


class HTTPGenericError(BaseModel):
    detail: str


class Tags(Enum):
    CLUSTERS = "clusters"
    NODES = "nodes"
    MISC = "misc"
    PORTS = "ports"


responses = {
    "5XX": {"description": "Unhandled server error", "model": HTTPGenericError},
}

not_found_responses = {
    status.HTTP_404_NOT_FOUND: {"description": "Object was not found", "model": HTTPGenericError},
}

already_exists_responses = {
    status.HTTP_409_CONFLICT: {"description": "Object already exists", "model": HTTPGenericError},
}

router = APIRouter()


@router.get("/", tags=[Tags.MISC], description="Returns golem-workers status and version.")
async def index():
    return {
        "name": "golem-workers",
        "version": __version__,
    }


@router.post(
    "/get-proposals",
    tags=[Tags.MISC],
    responses=responses,
    description=commands.GetProposalsCommand.__doc__,
)
async def get_proposals(
    request_data: Annotated[
        commands.GetProposalsRequest,
        Body(
            openapi_examples={
                "minimal_cpu": {
                    "summary": "Minimal CPU",
                    "description": "This example shows how to select providers for Virtual Machine.",
                    "value": {
                        "market_config": {
                            "demand": {
                                "payloads": ["golem_workers.payloads.ClusterNodePayload"],
                            },
                        },
                    },
                },
            }
        ),
    ],
    proposal_service: IProposalService = Depends(get_proposal_service),
) -> commands.GetProposalsResponse:
    proposals = await proposal_service.get_proposals(request_data)
    return commands.GetProposalsResponse(proposals=proposals)


@router.get("/cluster", tags=[Tags.CLUSTERS])
async def list_clusters(
    cluster_service: IClusterService = Depends(get_cluster_service),
) -> Annotated[List[str], Body(examples=[["cluster1", "cluster2"]])]:
    """
    Lists available clusters
    """
    return await cluster_service.list_clusters()


@router.post(
    "/cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **already_exists_responses},
    description=commands.CreateClusterCommand.__doc__,
)
async def create_cluster(
    request_data: Annotated[
        commands.CreateClusterRequest,
        Body(
            openapi_examples={
                "testnet_linear_budget_vpn_reputation": {
                    "summary": "Average usage budget, VPN and reputation (testnet)",
                    "description": "This example shows how to create a testnet cluster that support average usage budget, simple VPN network and Golem Reputation integration.",
                    "value": {
                        "cluster_id": "example",
                        "budget_types": {
                            "default": {
                                "budget": {
                                    "golem_workers.budgets.AveragePerCpuUsageLinearModelBudget": {
                                        "average_cpu_load": 1.0,
                                        "average_duration_hours": 0.5,
                                        "average_max_cost": 1.5,
                                    },
                                },
                                "scope": "cluster",
                            },
                        },
                        "network_types": {
                            "default": {
                                "ip": "192.168.0.0/16",
                            },
                        },
                    },
                },
            },
        ),
    ],
    cluster_service: IClusterService = Depends(get_cluster_service),
) -> commands.CreateClusterResponse:
    cluster = await cluster_service.create_cluster(request_data)
    return commands.CreateClusterResponse(cluster=cluster)


@router.get(
    "/cluster/{cluster_id}",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.GetClusterCommand.__doc__,
)
async def get_cluster(
    cluster_id: str,
    cluster_service: IClusterService = Depends(get_cluster_service),
) -> commands.GetClusterResponse:
    cluster = await cluster_service.get_cluster(cluster_id)
    return commands.GetClusterResponse(cluster=cluster)


@router.delete(
    "/cluster/{cluster_id}",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.DeleteClusterCommand.__doc__,
)
async def delete_cluster(
    cluster_id: str = Path(
        ...,
        title="Cluster ID",
        description="cluster identifier given in create-cluster operation",
        example="example",
    ),
    cluster_service: IClusterService = Depends(get_cluster_service),
) -> commands.DeleteClusterResponse:
    result = await cluster_service.delete_cluster(cluster_id)
    return commands.DeleteClusterResponse(cluster=result["cluster"])


@router.post(
    "/cluster/{cluster_id}/node",
    tags=[Tags.NODES],
    responses={
        **responses,
        **already_exists_responses,
    },
    description=commands.CreateNodeCommand.__doc__,
)
async def create_node(
    request_data: Annotated[
        commands.CreateNodeRequest,
        Body(
            openapi_examples={
                "echo_test": {
                    "summary": "modelserve/echo-test:2",
                    "description": "This example shows how to run echo test with VPN",
                    "value": {
                        "cluster_id": "example",
                        "node_networks": {
                            "default": {
                                "ip": None,
                            },
                        },
                        "node_config": {
                            "market_config": {
                                "demand": {
                                    "payloads": [
                                        {
                                            "golem_workers.payloads.ClusterNodePayload": {
                                                "image_tag": "modelserve/echo-test:2",
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        ),
    ],
    cluster_id: str = Path(
        ...,
        title="Cluster ID",
        description="Cluster to which the new node will be attached",
        example="example",
    ),
    node_service: INodeService = Depends(get_node_service),
) -> commands.CreateNodeResponse:
    node = await node_service.create_node(request_data)
    return commands.CreateNodeResponse(node=node)


@router.get(
    "/cluster/{cluster_id}/node/{node_id}",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.GetNodeCommand.__doc__,
)
async def get_node(
    cluster_id: str,
    node_id: str,
    node_service: INodeService = Depends(get_node_service),
) -> commands.GetNodeResponse:
    node = await node_service.get_node(cluster_id, node_id)
    return commands.GetNodeResponse(node=node)


@router.delete(
    "/cluster/{cluster_id}/node/{node_id}",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.DeleteNodeCommand.__doc__,
)
async def delete_node(
    cluster_id: str,
    node_id: str,
    node_service: INodeService = Depends(get_node_service),
) -> commands.DeleteNodeResponse:
    result = await node_service.delete_node(cluster_id, node_id)
    return commands.DeleteNodeResponse(node=result["node"])


@router.get(
    "/events",
    tags=[Tags.MISC],
    description="Server-Sent Events (SSE) endpoint for receiving real-time node events",
)
async def events(
    request: Request,
    node_id: Optional[str] = Query(None, description="Filter events by node ID"),
    cluster_id: Optional[str] = Query(None, description="Filter events by cluster ID"),
    event_types: Optional[List[str]] = Query(
        None,
        description="Filter events by event types (e.g. provisioning_started, started, stopped)",
    ),
):
    """
    SSE endpoint that streams events from node background tasks.

    Events include state changes (created, provisioning, provisioned, starting, started, stopping, stopped)
    and error conditions.

    You can filter events by node_id, cluster_id, and/or event_types.
    """
    return StreamingResponse(
        event_bus.get_events(node_id, cluster_id, event_types),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# Port allocation endpoints
class PortConfigRequest(BaseModel):
    min_port: int = Field(..., description="Minimum port number in allocation range", example=8050)
    max_port: int = Field(..., description="Maximum port number in allocation range", example=9999)
    expiration_minutes: Optional[int] = Field(
        5, description="Minutes until allocation expires", example=5
    )


class PortConfigResponse(BaseModel):
    min_port: int
    max_port: int
    expiration_minutes: int


class PortAllocationResponse(BaseModel):
    allocation_id: str
    port: int
    status: str
    expires_at: str


class PortUseRequest(BaseModel):
    allocation_id: str
    cluster_id: str
    node_id: str


class PortUseResponse(BaseModel):
    port: int
    status: str
    cluster_id: str
    node_id: str


class PortReleaseResponse(BaseModel):
    port: int
    status: str


class ClusterNodeReleaseRequest(BaseModel):
    cluster_id: str
    node_id: Optional[str] = None


class PortsReleasedResponse(BaseModel):
    released_ports: List[int]
    count: int


@router.get(
    "/ports/config",
    tags=[Tags.PORTS],
    responses=responses,
    description="Returns the current port allocation service configuration.",
)
async def get_port_config(
    port_service: IPortAllocationService = Depends(get_port_allocation_service)
) -> PortConfigResponse:
    """Get the current port allocation configuration."""
    return port_service.get_config()


@router.post(
    "/ports/allocate",
    tags=[Tags.PORTS],
    responses=responses,
    description="Allocates a random available port in the configured range.",
)
async def allocate_port(
    port_service: IPortAllocationService = Depends(get_port_allocation_service)
) -> PortAllocationResponse:
    """Allocate a random available port."""
    return port_service.allocate_port()


@router.post(
    "/ports/use",
    tags=[Tags.PORTS],
    responses={**responses, **not_found_responses},
    description="Assigns a previously allocated port to a specific cluster and node.",
)
async def use_port(
    request_data: PortUseRequest,
    port_service: IPortAllocationService = Depends(get_port_allocation_service),
) -> PortUseResponse:
    """Mark a port as in use by a specific cluster and node."""
    return port_service.use_port(
        request_data.allocation_id,
        request_data.cluster_id,
        request_data.node_id,
    )


@router.delete(
    "/ports/{allocation_id}",
    tags=[Tags.PORTS],
    responses={**responses, **not_found_responses},
    description="Releases a port back to the available pool.",
)
async def cancel_port_allocation(
    allocation_id: str,
    port_service: IPortAllocationService = Depends(get_port_allocation_service),
) -> PortReleaseResponse:
    """Cancel a port allocation and release the port."""
    return port_service.cancel_allocation(allocation_id)


@router.get(
    "/ports",
    tags=[Tags.PORTS],
    responses=responses,
    description="Lists all port allocations with optional filtering.",
)
async def list_port_allocations(
    port_service: IPortAllocationService = Depends(get_port_allocation_service),
    status: Optional[str] = Query(None, description="Filter by status (allocated or in_use)"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
) -> List[PortAllocationResponse]:
    """List all port allocations with optional filtering."""
    return port_service.list_allocations(status, cluster_id, node_id)


@router.get(
    "/ports/{allocation_id}",
    tags=[Tags.PORTS],
    responses={**responses, **not_found_responses},
    description="Returns details about a specific port allocation.",
)
async def get_port_allocation(
    allocation_id: str,
    port_service: IPortAllocationService = Depends(get_port_allocation_service),
) -> PortAllocationResponse:
    """Get details about a specific port allocation."""
    return port_service.get_allocation(allocation_id)


@router.delete(
    "/ports/release",
    tags=[Tags.PORTS],
    responses=responses,
    description="Releases all ports associated with a cluster or node.",
)
async def release_ports_by_cluster_node(
    request_data: ClusterNodeReleaseRequest,
    port_service: IPortAllocationService = Depends(get_port_allocation_service),
) -> PortsReleasedResponse:
    """Release all ports associated with a cluster or node."""
    return port_service.release_ports_by_cluster_node(
        request_data.cluster_id,
        request_data.node_id,
    )