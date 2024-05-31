import asyncio
import logging.config
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from golem.managers import (
    DefaultAgreementManager,
    DefaultProposalManager,
    DemandManager,
    NegotiatingPlugin,
    PaymentManager,
    PaymentPlatformNegotiator,
    ProposalBuffer,
)
from golem.node import GolemNode
from golem.utils.logging import DEFAULT_LOGGING
from ray_on_golem.server.services.golem import DriverListAllocationPaymentManager

from clusterapi.golem_helpers import (
    ClusterAPIDemandManager,
    NodeConfigNegotiator,
    ProposalGenHelper,
)
from clusterapi.models import ClusterConfig, CreateNodePayload, PayloadConfig

logging.config.dictConfig(DEFAULT_LOGGING)

storage: Dict[str, ClusterConfig] = {}
golem = GolemNode()
payment_manager: PaymentManager = DriverListAllocationPaymentManager(
    golem,
    budget=10,
    network="holesky",
)
demand_managers: List[DemandManager] = []


@asynccontextmanager
async def lifespan(cluster_api: FastAPI):
    async with golem:
        async with payment_manager:
            yield
            for manager in demand_managers[::-1]:
                # all demand.unsubscribe() are called when api is being shutdown
                await manager.stop()


cluster_api = FastAPI(lifespan=lifespan)


@cluster_api.get("/offers")
async def get_offers(payload_config: PayloadConfig):
    """Read proposals from Yagna marketplace based on given `payload_config`"""
    manager = ClusterAPIDemandManager(  # TODO `Refreshing` is an overkill
        golem,
        get_allocation=payment_manager.get_allocation,
        payloads=[payload_config.payload],
    )
    demand_managers.append(manager)
    await manager.start()
    await asyncio.sleep(1)
    offers = manager.get_initial_proposals()
    offers = [await o.get_proposal_data() for o in offers]
    return [
        {
            "proposal_id": o.proposal_id,
            "issuer_id": o.issuer_id,
            "state": o.state,
            "timestamp": o.timestamp,
            "prev_proposal_id": o.prev_proposal_id,
            "properties": o.properties,
            # "constraints": o.constraints,
        }
        for o in offers
    ]


@cluster_api.post("/cluster")
async def post_cluster(cluster_config: ClusterConfig):
    """Create cluster. Save given cluster configuration."""
    if cluster_config.id_ in storage:
        raise HTTPException(status_code=409, detail="Cluster config already exists")
    storage[cluster_config.id_] = cluster_config
    return cluster_config.id_


@cluster_api.patch("/cluster")
async def patch_cluster(cluster_config: ClusterConfig):
    """Updates cluster. Save given cluster configuration."""
    if cluster_config.id_ not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")
    storage[cluster_config.id_] = cluster_config
    return cluster_config.id_


@cluster_api.post("/cluster/{cluster_id}/node")
async def post_cluster_node(cluster_id: str, payload: CreateNodePayload):
    """Create node. Apply logic from cluster configuration."""
    if cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    cluster_config: ClusterConfig = storage[cluster_id]
    node_config_negotiator = NodeConfigNegotiator(cluster_config.node_config)
    await node_config_negotiator.setup()

    get_proposal_callable = ProposalGenHelper(golem, payload.proposal_ids)

    proposal_manager = DefaultProposalManager(
        golem,
        get_proposal_callable,
        plugins=(
            NegotiatingPlugin(
                proposal_negotiators=[
                    node_config_negotiator,
                    PaymentPlatformNegotiator(),
                ],
            ),
            ProposalBuffer(
                min_size=0,
                max_size=4,
                fill_concurrency_size=4,
            ),
        ),
    )
    agreement_manager = DefaultAgreementManager(golem, proposal_manager.get_draft_proposal)

    async with proposal_manager, agreement_manager:
        try:
            agreement = await agreement_manager.get_agreement()
        except StopAsyncIteration as err:
            raise HTTPException(status_code=400, detail=repr(err))

    return {"agreement_id": agreement.id}


@cluster_api.get("/cluster/{cluster_id}/node/{node_id}")
async def get_cluster_node(cluster_id: str, node_id: str):
    """Read node info and status"""
    ...


@cluster_api.delete("/cluster/{cluster_id}/node/{node_id}")
async def delete_cluster_node(cluster_id: str, node_id: str):
    """Delete cluster node."""
    ...


@cluster_api.get("/cluster/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Read cluster info and status."""
    ...
