from enum import Enum
from typing import List, Optional

from fastapi import Request, status, APIRouter, Body, Query
from fastapi.params import Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from golem_workers import commands, __version__
from golem_workers.commands import (
    GetClusterRequest,
    DeleteClusterRequest,
    GetNodeRequest,
    DeleteNodeRequest,
)
from golem_workers.events import event_bus


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
                "minimal_gpu": {
                    "summary": "Single GPU",
                    "description": "This example shows how to select providers for Virtual Machine with any GPU support.",
                    "value": {
                        "market_config": {
                            "demand": {
                                "payloads": [
                                    {
                                        "golem_workers.payloads.ClusterNodePayload": {
                                            "runtime": "vm-nvidia",
                                            "min_mem_gib": 16,
                                            "min_storage_gib": 20,
                                            "outbound_urls": [
                                                "https://gpu-provider.dev.golem.network",
                                            ],
                                        },
                                    },
                                ],
                                "constraints": [
                                    "golem.!exp.gap-35.v1.inf.gpu.model=*",
                                ],
                            },
                        },
                    },
                },
                "multi_gpu": {
                    "summary": "Multiple GPU",
                    "description": "This example shows how to select providers for Virtual Machine with multiple GPU support.",
                    "value": {
                        "market_config": {
                            "demand": {
                                "payloads": [
                                    {
                                        "golem_workers.payloads.ClusterNodePayload": {
                                            "runtime": "vm-nvidia",
                                            "min_mem_gib": 16,
                                            "min_storage_gib": 20,
                                            "outbound_urls": [
                                                "https://gpu-provider.dev.golem.network",
                                            ],
                                        },
                                    },
                                ],
                                "constraints": [
                                    "golem.!exp.gap-35.v1.inf.gpu.d0.quantity>=2",
                                ],
                            },
                        },
                    },
                },
            }
        ),
    ],
    request: Request,
) -> commands.GetProposalsResponse:
    command = await request.app.state.container.get_proposal_command()

    return await command(request_data)


@router.get("/cluster", tags=[Tags.CLUSTERS])
async def list_clusters(
    request: Request,
) -> Annotated[List[str], Body(examples=[["cluster1", "cluster2"]])]:
    """
    Lists available clusters
    """
    command = await request.app.state.container.list_cluster_command()
    return await command()


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
                    "description": "This example shows how to create a testnet cluster that support average usage budget, simple VPN network and Golem Reputation integration. Note that to use this example, integration with Golem Reputation is required at Golem Workers startup - refer to README for more information.",
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
                        "node_types": {
                            "default": {
                                "market_config": {
                                    "filters": [
                                        {
                                            "golem_reputation.ProviderBlacklistPlugin": {
                                                "payment_network": "holesky",
                                            },
                                        },
                                    ],
                                    "sorters": [
                                        {
                                            "golem_reputation.ReputationScorer": {
                                                "payment_network": "holesky",
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
                "mainnet_linear_budget_vpn_reputation": {
                    "summary": "Average usage budget, VPN and reputation (mainnet)",
                    "description": "This example shows how to create a mainnet cluster that support average usage budget, simple VPN network and Golem Reputation integration. Note that to use this example, integration with Golem Reputation is required at Golem Workers startup - refer to README for more information.",
                    "value": {
                        "cluster_id": "example",
                        "payment_config": {"network": "polygon"},
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
                        "node_types": {
                            "default": {
                                "market_config": {
                                    "filters": [
                                        {
                                            "golem_reputation.ProviderBlacklistPlugin": {
                                                "payment_network": "polygon",
                                            },
                                        },
                                    ],
                                    "sorters": [
                                        {
                                            "golem_reputation.ReputationScorer": {
                                                "payment_network": "polygon",
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
    request: Request,
) -> commands.CreateClusterResponse:
    command = await request.app.state.container.create_cluster_command()

    return await command(request_data)


@router.get(
    "/cluster/{cluster_id}",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.GetClusterCommand.__doc__,
)
async def get_cluster(
    request: Request,
    cluster_id: str,
) -> commands.GetClusterResponse:
    command = await request.app.state.container.get_cluster_command()
    request_data = GetClusterRequest(cluster_id=cluster_id)

    return await command(request_data)


@router.delete(
    "/cluster/{cluster_id}",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.DeleteClusterCommand.__doc__,
)
async def delete_cluster(
    request: Request,
    cluster_id: str = Path(
        ...,
        title="Cluster ID",
        description="cluster identifier given in create-cluster operation",
        example="example",
    ),
) -> commands.DeleteClusterResponse:
    command = await request.app.state.container.delete_cluster_command()

    return await command(DeleteClusterRequest(cluster_id=cluster_id))


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
                    "description": "This example shows how to run echo test. It will use a VPN and proxy traffic from local machine to running vm at http://localhost:8080.",
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
                            "on_start_commands": [
                                {
                                    "golem_workers.work.deploy_and_start_activity": {
                                        "deploy_timeout_minutes": 60,
                                    },
                                },
                                {
                                    "golem_workers.work.run_in_shell": [
                                        ["nginx"],
                                    ],
                                },
                            ],
                            "sidecars": [
                                {
                                    "golem_workers.sidecars.WebsocatPortTunnelSidecar": {
                                        "network_name": "default",
                                        "local_port": "8080",
                                        "remote_port": "80",
                                    },
                                },
                            ],
                        },
                    },
                },
                "automatic": {
                    "summary": "modelserve/automatic1111:4",
                    "description": "This example shows how to run automatic with example model image. Automatic will take few minutes to download example model from Huggingface to provider. It will use a VPN and proxy traffic from local machine to running vm at http://localhost:8080.",
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
                                                "runtime": "vm-nvidia",
                                                "image_tag": "modelserve/automatic1111:4",
                                                "outbound_urls": [
                                                    "https://gpu-provider.dev.golem.network",
                                                ],
                                            },
                                        },
                                    ],
                                },
                            },
                            "on_start_commands": [
                                {
                                    "golem_workers.work.deploy_and_start_activity": {
                                        "deploy_timeout_minutes": 60,
                                    },
                                },
                                {
                                    "golem_workers.work.prepare_and_run_ssh_server": {
                                        "ssh_private_key_path": "/tmp/ssh_key",
                                    },
                                },
                                {
                                    "golem_workers.work.run_in_shell": [
                                        "cd /usr/src/app/ && ./start.sh --model_url https://gpu-provider.dev.golem.network/models/v1-5-pruned-emaonly.safetensors > /usr/src/app/output/log 2>&1 &",
                                    ],
                                },
                            ],
                            "sidecars": [
                                {
                                    "golem_workers.sidecars.WebsocatPortTunnelSidecar": {
                                        "network_name": "default",
                                        "local_port": "8080",
                                        "remote_port": "8000",
                                    }
                                },
                                {
                                    "golem_workers.sidecars.WebsocatPortTunnelSidecar": {
                                        "network_name": "default",
                                        "local_port": "8081",
                                        "remote_port": "8001",
                                    },
                                },
                            ],
                        },
                    },
                },
            },
        ),
    ],
    request: Request,
    cluster_id: str = Path(
        ...,
        title="Cluster ID",
        description="Cluster to which the new node will be attached",
        example="example",
    ),
) -> commands.CreateNodeResponse:
    command = await request.app.state.container.create_node_command()

    return await command(request_data)


@router.get(
    "/cluster/{cluster_id}/node/{node_id}",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.GetNodeCommand.__doc__,
)
async def get_node(
    cluster_id: str,
    node_id: str,
    request: Request,
) -> commands.GetNodeResponse:
    command = await request.app.state.container.get_node_command()

    return await command(GetNodeRequest(cluster_id=cluster_id, node_id=node_id))


@router.delete(
    "/cluster/{cluster_id}/node/{node_id}",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.DeleteNodeCommand.__doc__,
)
async def delete_node(
    cluster_id: str,
    node_id: str,
    request: Request,
) -> commands.DeleteNodeResponse:
    command = await request.app.state.container.delete_node_command()

    return await command(DeleteNodeRequest(cluster_id=cluster_id, node_id=node_id))


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


# Add these models after the existing models
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


# Add these endpoints before the end of the file
@router.get(
    "/ports/config",
    tags=[Tags.PORTS],
    responses=responses,
    description="Returns the current port allocation service configuration.",
)
async def get_port_config(request: Request) -> PortConfigResponse:
    """Get the current port allocation configuration."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.get_config()


@router.post(
    "/ports/allocate",
    tags=[Tags.PORTS],
    responses=responses,
    description="Allocates a random available port in the configured range.",
)
async def allocate_port(request: Request) -> PortAllocationResponse:
    """Allocate a random available port."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.allocate_port()


@router.post(
    "/ports/use",
    tags=[Tags.PORTS],
    responses={**responses, **not_found_responses},
    description="Assigns a previously allocated port to a specific cluster and node.",
)
async def use_port(
    request_data: PortUseRequest,
    request: Request,
) -> PortUseResponse:
    """Mark a port as in use by a specific cluster and node."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.use_port(
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
    request: Request,
) -> PortReleaseResponse:
    """Cancel a port allocation and release the port."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.cancel_allocation(allocation_id)


@router.get(
    "/ports",
    tags=[Tags.PORTS],
    responses=responses,
    description="Lists all port allocations with optional filtering.",
)
async def list_port_allocations(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status (allocated or in_use)"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
) -> List[PortAllocationResponse]:
    """List all port allocations with optional filtering."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.list_allocations(status, cluster_id, node_id)


@router.get(
    "/ports/{allocation_id}",
    tags=[Tags.PORTS],
    responses={**responses, **not_found_responses},
    description="Returns details about a specific port allocation.",
)
async def get_port_allocation(
    allocation_id: str,
    request: Request,
) -> PortAllocationResponse:
    """Get details about a specific port allocation."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.get_allocation(allocation_id)


@router.delete(
    "/ports/release",
    tags=[Tags.PORTS],
    responses=responses,
    description="Releases all ports associated with a cluster or node.",
)
async def release_ports_by_cluster_node(
    request_data: ClusterNodeReleaseRequest,
    request: Request,
) -> PortsReleasedResponse:
    """Release all ports associated with a cluster or node."""
    manager = await request.app.state.container.get_port_allocation_manager()
    return manager.release_ports_by_cluster_node(
        request_data.cluster_id,
        request_data.node_id,
    )
