from enum import Enum
from fastapi import Request, status, APIRouter
from pydantic import BaseModel

from golem_workers import commands


class HTTPGenericError(BaseModel):
    detail: str


class Tags(Enum):
    PROPOSALS = "proposals"
    CLUSTERS = "clusters"
    NODES = "nodes"


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


@router.post(
    "/get-proposals",
    tags=[Tags.PROPOSALS],
    responses=responses,
    description=commands.GetProposalsCommand.__doc__,
)
async def get_proposals(
    request_data: commands.GetProposalsRequest, request: Request
) -> commands.GetProposalsResponse:
    command = await request.app.state.container.get_proposal_command()

    return await command(request_data)


@router.post(
    "/create-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **already_exists_responses},
    description=commands.CreateClusterCommand.__doc__,
)
async def create_cluster(
    request_data: commands.CreateClusterRequest, request: Request
) -> commands.CreateClusterResponse:
    command = await request.app.state.container.create_cluster_command()

    return await command(request_data)


@router.post(
    "/get-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.GetClusterCommand.__doc__,
)
async def get_cluster(
    request_data: commands.GetClusterRequest, request: Request
) -> commands.GetClusterResponse:
    command = await request.app.state.container.get_cluster_command()

    return await command(request_data)


@router.post(
    "/delete-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=commands.DeleteClusterCommand.__doc__,
)
async def delete_cluster(
    request_data: commands.DeleteClusterRequest, request: Request
) -> commands.DeleteClusterResponse:
    command = await request.app.state.container.delete_cluster_command()

    return await command(request_data)


@router.post(
    "/create-node",
    tags=[Tags.NODES],
    responses={
        **responses,
        **already_exists_responses,
    },
    description=commands.CreateNodeCommand.__doc__,
)
async def create_node(
    request_data: commands.CreateNodeRequest, request: Request
) -> commands.CreateNodeResponse:
    command = await request.app.state.container.create_node_command()

    return await command(request_data)


@router.post(
    "/get-node",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.GetNodeCommand.__doc__,
)
async def get_node(
    request_data: commands.GetNodeRequest, request: Request
) -> commands.GetNodeResponse:
    command = await request.app.state.container.get_node_command()

    return await command(request_data)


@router.post(
    "/delete-node",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=commands.DeleteNodeCommand.__doc__,
)
async def delete_node(
    request_data: commands.DeleteNodeRequest, request: Request
) -> commands.DeleteNodeResponse:
    command = await request.app.state.container.delete_node_command()

    return await command(request_data)
