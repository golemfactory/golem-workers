import asyncio
import logging.config
from contextlib import asynccontextmanager, AsyncExitStack
from datetime import timedelta
from fastapi import FastAPI, HTTPException, status, Request
from typing import Dict, List

from golem.managers import (
    PaymentManager, NegotiatingPlugin, PaymentPlatformNegotiator,
)
from golem.node import GolemNode
from golem.resources import Demand, Proposal
from golem.utils.logging import DEFAULT_LOGGING
from golem_cluster_api.cluster.cluster import Cluster
from golem_cluster_api.golem import (
    DriverListAllocationPaymentManager, NodeConfigNegotiator,
)
from golem_cluster_api.models import (
    CreateClusterRequest,
    CreateNodeRequest,
    DeleteClusterRequest,
    GetClusterRequest,
    GetNodeRequest,
    GetProposalsRequest,
    CreateClusterResponse,
    GetClusterResponse,
    DeleteClusterResponse,
    GetProposalsResponse,
    ClusterOut,
    ProposalOut, CreateNodeResponse, NodeOut, DeleteNodeRequest, DeleteNodeResponse, GetNodeResponse,
)
from golem_cluster_api.settings import Settings
from golem_cluster_api.utils import collect_initial_proposals

logging.config.dictConfig(DEFAULT_LOGGING)

# TODO MVP: use ClusterRepository instead of global variables
clusters: Dict[str, Cluster] = {}
clusters_lock = asyncio.Lock()

settings = Settings()

# TODO MVP: use DemandRepository instead of global variables
demands: List[Demand] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    golem_node = GolemNode(app_key=settings.yagna_appkey)

    # TODO POC: Move to cluster
    payment_manager: PaymentManager = DriverListAllocationPaymentManager(
        golem_node,

        # TODO POC: Use user config instead
        budget=10,
        network="holesky",
    )

    app.state.golem_node = golem_node
    app.state.payment_manager = payment_manager

    async with AsyncExitStack() as astack:
        await astack.enter_async_context(golem_node)
        await astack.enter_async_context(payment_manager)

        yield

        for cluster in clusters.values():
            await cluster.stop()

        for demand in demands[::-1]:
            # all demand.unsubscribe() are called when api is being shutdown
            await demand.unsubscribe()


app = FastAPI(lifespan=lifespan)


@app.post("/get-proposals")
async def get_proposals(request_data: GetProposalsRequest, request: Request) -> GetProposalsResponse:
    """Read proposals from Yagna marketplace based on given `payload_config`"""

    golem_node = request.app.state.golem_node
    payment_manager = request.app.state.payment_manager

    allocation = await payment_manager.get_allocation()
    demand_builder = await request_data.market_config.demand.create_demand_builder(allocation)
    demand = await demand_builder.create_demand(golem_node)
    demands.append(demand)  # TODO MVP: Unsubscribe demand after 5 minutes instead of end of the lifetime

    initial_proposals_data = await collect_initial_proposals(demand, timeout=timedelta(
        seconds=request_data.collection_time_seconds))

    return GetProposalsResponse(
        proposals=[
            ProposalOut(
                proposal_id=proposal_data.proposal_id,
                issuer_id=proposal_data.issuer_id,
                state=proposal_data.state,
                timestamp=proposal_data.timestamp,
                properties=proposal_data.properties,
            ) for proposal_data in initial_proposals_data
        ],
    )


@app.post("/create-cluster")
async def create_cluster(request_data: CreateClusterRequest) -> CreateClusterResponse:
    """Create cluster. Save given cluster configuration."""

    async with clusters_lock:
        if request_data.cluster_id in clusters:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cluster with id `{request_data.cluster_id}` already exists!"
            )

        # TODO: Use ClusterRepository for creation scheduling
        clusters[request_data.cluster_id] = cluster = Cluster(
            cluster_id=request_data.cluster_id,
            payment_config=request_data.payment_config,
            node_types=request_data.node_types,
        )

        cluster.schedule_start()

        return CreateClusterResponse(
            cluster=ClusterOut.from_cluster(cluster),
        )


@app.post("/get-cluster")
async def get_cluster(request_data: GetClusterRequest) -> GetClusterResponse:
    """Read cluster info and status."""

    cluster = clusters.get(request_data.cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cluster with id `{request_data.cluster_id}` does not exists!",
        )

    return GetClusterResponse(
        cluster=ClusterOut.from_cluster(cluster),
    )


@app.post("/delete-cluster")
async def delete_cluster(request_data: DeleteClusterRequest) -> DeleteClusterResponse:
    """Read cluster info and status."""
    async with clusters_lock:
        cluster = clusters.get(request_data.cluster_id)

        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster with id `{request_data.cluster_id}` does not exists!"
            )

        # TODO: use schedule stop and remove instead of inline waiting
        # TODO: Use ClusterRepository for deletion scheduling
        await cluster.stop()

        del clusters[request_data.cluster_id]

        return DeleteClusterResponse(
            cluster=ClusterOut.from_cluster(cluster),
        )


@app.post("/create-node")
async def create_node(request_data: CreateNodeRequest, request: Request) -> CreateNodeResponse:
    """Create node. Apply logic from cluster configuration."""
    cluster = clusters.get(request_data.cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster with id `{request_data.cluster_id}` does not exists!"
        )

    # TODO MVP: Handle not existing proposal id
    initial_proposal = Proposal(request.app.state.golem_node, request_data.proposal_id)

    node_config = cluster.get_node_type_config(request_data.node_type)
    node_config = node_config.combine(request_data.node_config)

    negotiating_plugin = NegotiatingPlugin(
        proposal_negotiators=(
            NodeConfigNegotiator(node_config.market_config),
            PaymentPlatformNegotiator(),
        ),
    )

    demand_data = await initial_proposal.demand.get_demand_data()
    draft_proposal = await negotiating_plugin._negotiate_proposal(demand_data, initial_proposal)

    # TODO POC: close agreements
    agreement = await draft_proposal.create_agreement()
    await agreement.confirm()
    await agreement.wait_for_approval()
    activity = await agreement.create_activity()

    # TODO: Use ClusterRepository for creation scheduling
    node = cluster.create_node(activity)

    return CreateNodeResponse(
        node=NodeOut.from_node(node),
    )


@app.post("/get-node")
async def get_node(request_data: GetNodeRequest) -> GetNodeResponse:
    """Read node info and status"""
    cluster = clusters.get(request_data.cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster with id `{request_data.cluster_id}` does not exists!"
        )

    node = cluster.nodes.get(request_data.node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id `{request_data.node_id}` does not exists in cluster!"
        )

    return GetNodeResponse(
        node=NodeOut.from_node(node),
    )


@app.post("/delete-node")
async def delete_node(request_data: DeleteNodeRequest) -> DeleteNodeResponse:
    cluster = clusters.get(request_data.cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster with id `{request_data.cluster_id}` does not exists!"
        )

    node = cluster.nodes.get(request_data.node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id `{request_data.node_id}` does not exists in cluster!"
        )

    # TODO: Use ClusterRepository for deletion scheduling
    await cluster.delete_node(node)

    return DeleteNodeResponse(
        node=NodeOut.from_node(node),
    )