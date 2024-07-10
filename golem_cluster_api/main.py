from copy import deepcopy

import asyncio
import logging.config
from contextlib import asynccontextmanager
from enum import Enum
from fastapi import FastAPI, Request, status
from pydantic import BaseModel
from starlette.responses import JSONResponse
from typing import Dict, List

from golem.node import GolemNode
from golem.resources import Demand
from golem.utils.logging import DEFAULT_LOGGING
from golem_cluster_api.cluster import Cluster
from golem_cluster_api.commands import (
    GetProposalsCommand,
    GetProposalsRequest,
    GetProposalsResponse,
    CreateClusterCommand,
    CreateClusterRequest,
    CreateClusterResponse,
    GetClusterCommand,
    GetClusterRequest,
    GetClusterResponse,
    DeleteClusterCommand,
    DeleteClusterRequest,
    DeleteClusterResponse,
    CreateNodeRequest,
    CreateNodeResponse,
    CreateNodeCommand,
    GetNodeRequest,
    GetNodeResponse,
    GetNodeCommand,
    DeleteNodeCommand,
    DeleteNodeRequest,
    DeleteNodeResponse,
)
from golem_cluster_api.exceptions import (
    ClusterApiError,
    ObjectAlreadyExists,
    ObjectNotFound,
)
from golem_cluster_api.golem import DriverListAllocationPaymentManager
from golem_cluster_api.settings import Settings


logging_config = deepcopy(DEFAULT_LOGGING)
logging_config.update(
    {
        "loggers": {
            "golem_cluster_api": {
                "level": "DEBUG",
            },
        },
    }
)

logging.config.dictConfig(logging_config)


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

# TODO MVP: use ClusterRepository instead of global variables
clusters: Dict[str, Cluster] = {}
clusters_lock = asyncio.Lock()

settings = Settings()

# TODO MVP: use DemandRepository instead of global variables
demands: List[Demand] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    golem_node = GolemNode(app_key=settings.yagna_appkey)

    app.state.golem_node = golem_node

    async with golem_node:
        yield

        for cluster in clusters.values():
            await cluster.stop()

        for demand in demands[::-1]:
            # all demand.unsubscribe() are called when api is being shutdown
            await demand.unsubscribe()


app = FastAPI(
    title="Cluster API Specification",
    lifespan=lifespan,
)


@app.exception_handler(ClusterApiError)
async def cluster_api_error_handler(request: Request, exc: ClusterApiError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Unhandled server error! {exc}"},
    )


@app.exception_handler(ObjectNotFound)
async def object_not_found_handler(request: Request, exc: ClusterApiError):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ObjectAlreadyExists)
async def object_already_exists_handler(request: Request, exc: ClusterApiError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.post(
    "/get-proposals",
    tags=[Tags.PROPOSALS],
    responses=responses,
    description=GetProposalsCommand.__doc__,
)
async def get_proposals(
    request_data: GetProposalsRequest, request: Request
) -> GetProposalsResponse:
    golem_node = request.app.state.golem_node

    command = GetProposalsCommand(golem_node, DriverListAllocationPaymentManager)

    return await command(request_data)


@app.post(
    "/create-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **already_exists_responses},
    description=CreateClusterCommand.__doc__,
)
async def create_cluster(
    request_data: CreateClusterRequest, request: Request
) -> CreateClusterResponse:
    golem_node = request.app.state.golem_node

    command = CreateClusterCommand(golem_node, clusters_lock, clusters)

    return await command(request_data)


@app.post(
    "/get-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=GetClusterCommand.__doc__,
)
async def get_cluster(request_data: GetClusterRequest) -> GetClusterResponse:
    command = GetClusterCommand(clusters)

    return await command(request_data)


@app.post(
    "/delete-cluster",
    tags=[Tags.CLUSTERS],
    responses={**responses, **not_found_responses},
    description=DeleteClusterCommand.__doc__,
)
async def delete_cluster(request_data: DeleteClusterRequest) -> DeleteClusterResponse:
    command = DeleteClusterCommand(clusters_lock, clusters)

    return await command(request_data)


@app.post(
    "/create-node",
    tags=[Tags.NODES],
    responses={
        **responses,
        **already_exists_responses,
    },
    description=CreateNodeCommand.__doc__,
)
async def create_node(request_data: CreateNodeRequest, request: Request) -> CreateNodeResponse:
    golem_node = request.app.state.golem_node
    command = CreateNodeCommand(golem_node, clusters)

    return await command(request_data)


@app.post(
    "/get-node",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=GetNodeCommand.__doc__,
)
async def get_node(request_data: GetNodeRequest) -> GetNodeResponse:
    command = GetNodeCommand(clusters)

    return await command(request_data)


@app.post(
    "/delete-node",
    tags=[Tags.NODES],
    responses={**responses, **not_found_responses},
    description=DeleteNodeCommand.__doc__,
)
async def delete_node(request_data: DeleteNodeRequest) -> DeleteNodeResponse:
    command = DeleteNodeCommand(clusters)

    return await command(request_data)
