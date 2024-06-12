from dataclasses import asdict

import asyncio
import logging.config
from contextlib import asynccontextmanager, AsyncExitStack
from datetime import timedelta
from fastapi import FastAPI, HTTPException, status, Request
from typing import Dict, List

from golem.managers import (
    PaymentManager,
)
from golem.node import GolemNode
from golem.resources import Demand
from golem.utils.logging import DEFAULT_LOGGING
from golem_cluster_api.cluster.cluster import Cluster
from golem_cluster_api.golem import (
    DriverListAllocationPaymentManager,
)
from golem_cluster_api.models import (
    CreateClusterRequest,
    CreateNodesBody,
    DeleteClusterRequest,
    DeleteNodeBody,
    ExecuteCommandsBody,
    GetClusterRequest,
    GetCommandsBody,
    GetNodeBody,
    GetProposalsRequest,
    CreateClusterResponse,
    GetClusterResponse,
    DeleteClusterResponse,
    GetProposalsResponse,
    ClusterOut,
    ProposalOut,
)
from golem_cluster_api.settings import Settings
from golem_cluster_api.utils import prepare_demand, collect_initial_proposals

logging.config.dictConfig(DEFAULT_LOGGING)

# FIXME: use ClusterRepository instead of global variables
clusters: Dict[str, Cluster] = {}
clusters_lock = asyncio.Lock()


settings = Settings()


# FIXME: use DemandRepository instead of global variables
demands: List[Demand] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    golem_node = GolemNode(app_key=settings.yagna_appkey)
    payment_manager: PaymentManager = DriverListAllocationPaymentManager(
        golem_node,
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
    demand = await prepare_demand(
        golem_node, allocation, request_data.market_config.demand,
    )
    demands.append(demand)  # TODO: Unsubscribe demand after 5 minutes instead of end of the lifetime

    initial_proposals_data = await collect_initial_proposals(demand, timeout=timedelta(seconds=request_data.collection_time_seconds))

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

        clusters[request_data.cluster_id] = cluster = Cluster(
            name=request_data.cluster_id,
            payment_config=request_data.payment_config,
            node_types=request_data.node_types,
        )

        cluster.schedule_start()

        return CreateClusterResponse(
            cluster=ClusterOut(
                cluster_id=cluster.name,
            ),
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
        cluster=ClusterOut(
            cluster_id=cluster.name,
        ),
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
        await cluster.stop()

        del clusters[request_data.cluster_id]

        return DeleteClusterResponse(
            cluster=ClusterOut(
                cluster_id=cluster.name,
            )
        )


@app.post("/create-nodes")
async def create_nodes(body: CreateNodesBody):
    """Create node. Apply logic from cluster configuration."""
    # if body.cluster_id not in clusters:
    #     raise HTTPException(status_code=404, detail="Cluster config does not exists")
    #
    # node_config_data: NodeConfig = clusters[body.cluster_id]._provider_parameters.node_config
    # node_config_negotiator = NodeConfigNegotiator(node_config_data)
    # await node_config_negotiator.setup()
    #
    # if body.cluster_id not in proposal_manager:
    #     proposal_manager[body.cluster_id] = DefaultProposalManager(
    #         golem,
    #         ProposalPool(golem, body.proposal_ids).get_proposal,
    #         plugins=(
    #             NegotiatingPlugin(
    #                 proposal_negotiators=[
    #                     node_config_negotiator,
    #                     PaymentPlatformNegotiator(),
    #                 ],
    #             ),
    #             ProposalBuffer(
    #                 min_size=0,
    #                 max_size=2,
    #                 fill_concurrency_size=2,
    #             ),
    #         ),
    #     )
    #     agreement_manager[body.cluster_id] = DefaultAgreementManager(
    #         golem, proposal_manager[body.cluster_id].get_draft_proposal
    #     )
    #
    #     await proposal_manager[body.cluster_id].start()
    #     await agreement_manager[body.cluster_id].start()
    #
    # await clusters[body.cluster_id].request_nodes(
    #     node_config=clusters[body.cluster_id]._provider_parameters.node_config,
    #     count=body.node_count,
    #     tags={},
    #     get_agreement=agreement_manager[body.cluster_id].get_agreement,
    # )
    #
    # return {"nodes": clusters[body.cluster_id].nodes}


@app.post("/get-node")
async def get_node(body: GetNodeBody):
    """Read node info and status"""
    ...


@app.post("/delete-node")
async def delete_node(body: DeleteNodeBody):
    ...


@app.post("/execute-commands")
async def execute_commands(body: ExecuteCommandsBody):
    ...


@app.post("/get-commands-result")
async def get_command_result(body: GetCommandsBody):
    ...
