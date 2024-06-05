import asyncio
import logging.config
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from golem.exceptions import GolemException
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

from clusterapi.golem import ClusterAPIDemandManager, NodeConfigNegotiator, ProposalPool
from clusterapi.models import (
    CreateClusterBody,
    CreateNodesBody,
    CreateProposalPoolBody,
    DeleteClusterBody,
    DeleteNodeBody,
    DeleteProposalPoolBody,
    ExecuteCommandsBody,
    GetClusterBody,
    GetCommandsBody,
    GetNodeBody,
    GetProposalsBody,
    NodeConfig,
)

logging.config.dictConfig(DEFAULT_LOGGING)

storage: Dict[str, NodeConfig] = {}  # TODO store more then just `NodeConfig`
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


@cluster_api.post("/get-proposals")
async def get_proposals(body: GetProposalsBody):
    """Read proposals from Yagna marketplace based on given `payload_config`"""
    # We need manager so it unsubscribe Demands at the end
    manager = ClusterAPIDemandManager(  # TODO `Refreshing` is an overkill
        golem,
        get_allocation=payment_manager.get_allocation,
        payloads=body.node_config.custom_payloads,
    )
    demand_managers.append(manager)
    await manager.start()
    await asyncio.sleep(0.5)

    # TODO add proposal manager + way to get all items within the buffer (use buffer maybe)

    proposals = manager.get_initial_proposals()
    proposals = [await o.get_proposal_data() for o in proposals]
    return [
        {
            "proposal_id": p.proposal_id,
            "issuer_id": p.issuer_id,
            "state": p.state,
            "timestamp": p.timestamp,
            "prev_proposal_id": p.prev_proposal_id,
            "properties": p.properties,
            "constraints": p.constraints.serialize(),
        }
        for p in proposals
    ]


@cluster_api.post("/create-proposal-pool")
async def create_proposal_pool(body: CreateProposalPoolBody):
    ...


@cluster_api.post("/delete-proposal-pool")
async def delete_proposal_pool(body: DeleteProposalPoolBody):
    ...


@cluster_api.post("/create-cluster")
async def create_cluster(body: CreateClusterBody):
    """Create cluster. Save given cluster configuration."""
    if body.cluster_id in storage:
        raise HTTPException(status_code=409, detail="Cluster config already exists")
    storage[body.cluster_id] = body.node_config
    return body.cluster_id


@cluster_api.post("/get-cluster")
async def get_cluster(body: GetClusterBody):
    """Read cluster info and status."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    return storage[body.cluster_id]


@cluster_api.post("/delete-cluster")
async def delete_cluster(body: DeleteClusterBody):
    """Read cluster info and status."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    del storage[body.cluster_id]


@cluster_api.post("/create-nodes")
async def create_nodes(body: CreateNodesBody):
    """Create node. Apply logic from cluster configuration."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    node_config: NodeConfig = storage[body.cluster_id]
    node_config_negotiator = NodeConfigNegotiator(node_config.node_config_data)
    await node_config_negotiator.setup()

    proposal_manager = DefaultProposalManager(
        golem,
        ProposalPool(golem, body.proposal_ids).get_proposal,
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
                fill_concurrency_size=2,
            ),
        ),
    )
    agreement_manager = DefaultAgreementManager(golem, proposal_manager.get_draft_proposal)

    async with proposal_manager, agreement_manager:
        try:
            agreement = await agreement_manager.get_agreement()
        except GolemException as err:
            raise HTTPException(status_code=400, detail=repr(err))

    return {"agreement_id": agreement.id}


@cluster_api.post("/get-node")
async def get_node(body: GetNodeBody):
    """Read node info and status"""
    ...


@cluster_api.post("/delete-node")
async def delete_node(body: DeleteNodeBody):
    ...


@cluster_api.post("/execute-commands")
async def execute_commands(body: ExecuteCommandsBody):
    ...


@cluster_api.post("/get-commands-result")
async def get_command_result(body: GetCommandsBody):
    ...
