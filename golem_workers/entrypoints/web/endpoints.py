from enum import Enum
from typing import List

from fastapi import Request, status, APIRouter, Body
from fastapi.params import Path
from pydantic import BaseModel
from typing_extensions import Annotated

from golem_workers import commands, __version__
from golem_workers.commands import (
    GetClusterRequest,
    DeleteClusterRequest,
    GetNodeRequest,
    DeleteNodeRequest,
)


class HTTPGenericError(BaseModel):
    detail: str


class Tags(Enum):
    CLUSTERS = "clusters"
    NODES = "nodes"
    MISC = "misc"


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
