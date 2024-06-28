import asyncio
import logging.config
from contextlib import asynccontextmanager
from enum import Enum
from fastapi import FastAPI, HTTPException, Request, status
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
from golem_cluster_api.exceptions import ClusterApiError, ObjectAlreadyExists, ObjectNotFound
from golem_cluster_api.golem import DriverListAllocationPaymentManager
from golem_cluster_api.settings import Settings

logging.config.dictConfig(DEFAULT_LOGGING)


class ErrorMessage(BaseModel):
    message: str


class Tags(Enum):
    PROPOSALS = "proposals"
    CLUSTERS = "clusters"
    NODES = "nodes"


responses = {500: {"description": "Error Response", "model": ErrorMessage}}

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


app = FastAPI(lifespan=lifespan)


@app.exception_handler(ClusterApiError)
async def cluster_api_error_handler(request: Request, exc: ClusterApiError):
    return JSONResponse(status_code=500, content={"message": f"Unhandled server error! {exc}"})


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

    command = GetProposalsCommand(golem_node, demands, DriverListAllocationPaymentManager)

    return await command(request_data)


@app.post(
    "/create-cluster",
    tags=[Tags.CLUSTERS],
    responses=responses,
    description=CreateClusterCommand.__doc__,
)
async def create_cluster(
    request_data: CreateClusterRequest, request: Request
) -> CreateClusterResponse:
    golem_node = request.app.state.golem_node

    command = CreateClusterCommand(golem_node, clusters_lock, clusters)

    try:
        return await command(request_data)
    except ObjectAlreadyExists as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@app.post(
    "/get-cluster",
    tags=[Tags.CLUSTERS],
    responses=responses,
    description=GetClusterCommand.__doc__,
)
async def get_cluster(request_data: GetClusterRequest) -> GetClusterResponse:
    command = GetClusterCommand(clusters)

    try:
        return await command(request_data)
    except ObjectNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post(
    "/delete-cluster",
    tags=[Tags.CLUSTERS],
    responses=responses,
    description=DeleteClusterCommand.__doc__,
)
async def delete_cluster(request_data: DeleteClusterRequest) -> DeleteClusterResponse:
    command = DeleteClusterCommand(clusters_lock, clusters)

    try:
        return await command(request_data)
    except ObjectNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post(
    "/create-node",
    tags=[Tags.NODES],
    responses=responses,
    description=CreateNodeCommand.__doc__,
)
async def create_node(request_data: CreateNodeRequest, request: Request) -> CreateNodeResponse:
    golem_node = request.app.state.golem_node
    command = CreateNodeCommand(golem_node, clusters)

    try:
        return await command(request_data)
    except ObjectNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post(
    "/get-node",
    tags=[Tags.NODES],
    responses=responses,
    description=GetNodeCommand.__doc__,
)
async def get_node(request_data: GetNodeRequest) -> GetNodeResponse:
    command = GetNodeCommand(clusters)

    try:
        return await command(request_data)
    except ObjectNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post(
    "/delete-node",
    tags=[Tags.NODES],
    responses=responses,
    description=DeleteNodeCommand.__doc__,
)
async def delete_node(request_data: DeleteNodeRequest) -> DeleteNodeResponse:
    command = DeleteNodeCommand(clusters)

    try:
        return await command(request_data)
    except ObjectNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
