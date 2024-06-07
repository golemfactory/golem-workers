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
from ray_on_golem.server.settings import WEBSOCAT_PATH

from clusterapi.golem import (
    ClusterAIPCluster,
    ClusterAPIDemandManager,
    ClusterAPIGolemService,
    NodeConfigNegotiator,
    ProposalPool,
)
from clusterapi.models import (
    ClusterParametersData,
    CreateClusterBody,
    CreateNodesBody,
    DeleteClusterBody,
    DeleteNodeBody,
    ExecuteCommandsBody,
    GetClusterBody,
    GetCommandsBody,
    GetNodeBody,
    GetProposalsBody,
    NodeConfig,
)

logging.config.dictConfig(DEFAULT_LOGGING)

SSH_KEY_USER = "lucjan"
SSH_KEY_PATH = "/home/lucjan/.local/share/ray_on_golem/ray_on_golem_rsa_2b6976a4b5.pub"

storage: Dict[str, ClusterAIPCluster] = {}  # TODO store more then just `NodeConfig`
golem = GolemNode()
payment_manager: PaymentManager = DriverListAllocationPaymentManager(
    golem,
    budget=10,
    network="holesky",
)
demand_managers: List[DemandManager] = []

proposal_manager: Dict[str, DefaultProposalManager] = {}
agreement_manager: Dict[str, DefaultAgreementManager] = {}


@asynccontextmanager
async def lifespan(cluster_api: FastAPI):
    async with golem:
        async with payment_manager:
            yield
            for id_, manager in proposal_manager.items():
                await manager.stop()
            for id_, manager in agreement_manager.items():
                await manager.stop()
            for id_, cluster in storage.items():
                await cluster.stop()
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
    await asyncio.sleep(1)

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


@cluster_api.post("/create-cluster")
async def create_cluster(body: CreateClusterBody):
    """Create cluster. Save given cluster configuration."""
    if body.cluster_id in storage:
        raise HTTPException(status_code=409, detail="Cluster config already exists")
    golem_service = ClusterAPIGolemService(
        websocat_path=WEBSOCAT_PATH, registry_stats=False, golem_node=golem
    )
    await golem_service.init()
    storage[body.cluster_id] = ClusterAIPCluster(
        golem_service=golem_service,
        webserver_port=4578,
        name=body.cluster_id,
        provider_parameters=ClusterParametersData(
            webserver_port=4578,
            enable_registry_stats=False,
            payment_network="",  # TODO rm
            payment_driver="",  # TODO rm
            total_budget=5.0,  # TODO rm
            node_config=body.node_config.node_config_data,
            ssh_private_key=SSH_KEY_PATH,
            ssh_user=SSH_KEY_USER,
        ),
    )
    await storage[body.cluster_id].start()

    # storage[body.cluster_id] = body.node_config
    return body.cluster_id


@cluster_api.post("/get-cluster")
async def get_cluster(body: GetClusterBody):
    """Read cluster info and status."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    return {"nodes": storage[body.cluster_id].nodes}


@cluster_api.post("/delete-cluster")
async def delete_cluster(body: DeleteClusterBody):
    """Read cluster info and status."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    await storage[body.cluster_id].stop()
    del storage[body.cluster_id]


@cluster_api.post("/create-nodes")
async def create_nodes(body: CreateNodesBody):
    """Create node. Apply logic from cluster configuration."""
    if body.cluster_id not in storage:
        raise HTTPException(status_code=404, detail="Cluster config does not exists")

    node_config_data: NodeConfig = storage[body.cluster_id]._provider_parameters.node_config
    node_config_negotiator = NodeConfigNegotiator(node_config_data)
    await node_config_negotiator.setup()

    if body.cluster_id not in proposal_manager:
        proposal_manager[body.cluster_id] = DefaultProposalManager(
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
                    max_size=2,
                    fill_concurrency_size=2,
                ),
            ),
        )
        agreement_manager[body.cluster_id] = DefaultAgreementManager(
            golem, proposal_manager[body.cluster_id].get_draft_proposal
        )

        await proposal_manager[body.cluster_id].start()
        await agreement_manager[body.cluster_id].start()

    await storage[body.cluster_id].request_nodes(
        node_config=storage[body.cluster_id]._provider_parameters.node_config,
        count=body.node_count,
        tags={},
        get_agreement=agreement_manager[body.cluster_id].get_agreement,
    )

    return {"nodes": storage[body.cluster_id].nodes}


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
