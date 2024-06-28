from pydantic import Field
from typing import Mapping, List

from golem.managers import NegotiatingPlugin, PaymentPlatformNegotiator
from golem.node import GolemNode
from golem.resources import Proposal, Agreement, DemandBuilder, Activity
from golem_cluster_api.cluster import Cluster, Sidecar
from golem_cluster_api.commands.base import CommandResponse, CommandRequest, Command
from golem_cluster_api.exceptions import ObjectNotFound
from golem_cluster_api.golem import NodeConfigNegotiator
from golem_cluster_api.models import NodeConfig, NodeOut


class CreateNodeRequest(CommandRequest):
    cluster_id: str
    proposal_id: str
    node_type: str
    node_config: NodeConfig = Field(default_factory=NodeConfig)


class CreateNodeResponse(CommandResponse):
    node: NodeOut


class CreateNodeCommand(Command[CreateNodeRequest, CreateNodeResponse]):
    """Creates node. Apply logic from cluster configuration."""

    def __init__(
        self,
        golem_node: GolemNode,
        clusters: Mapping[str, Cluster],
    ) -> None:
        self._golem_node = golem_node

        self._clusters = clusters

    async def __call__(self, request: CreateNodeRequest) -> CreateNodeResponse:
        """
        Raises:
            ObjectNotFound: If given `cluster_id` is not found in cluster collection.
        """

        cluster = self._clusters.get(request.cluster_id)

        if not cluster:
            raise ObjectNotFound(f"Cluster with id `{request.cluster_id}` does not exists!")

        node_config = self._prepare_node_config(cluster, request)

        demand_builder = await self._prepare_demand_builder(cluster, node_config)

        draft_proposal = await self._negotiate_initial_proposal(request, demand_builder)

        activity = await self._create_activity(draft_proposal)

        node_ip = await cluster.network.create_node(await draft_proposal.get_provider_id())

        sidecars = self._prepare_sidecars(node_config)

        # TODO: Use ClusterRepository for creation scheduling
        node = cluster.create_node(
            activity,
            node_ip,
            on_start_commands=node_config.on_start_commands,
            on_stop_commands=node_config.on_stop_commands,
            sidecars=sidecars,
        )

        return CreateNodeResponse(
            node=NodeOut.from_node(node),
        )

    def _prepare_node_config(self, cluster: Cluster, request: CreateNodeRequest, ) -> NodeConfig:
        # TODO MVP: validate initially optional, but required for activity creation (for e.g. image url)
        node_config = cluster.get_node_type_config(request.node_type)
        return node_config.combine(request.node_config)


    async def _prepare_demand_builder(self, cluster: Cluster, node_config: NodeConfig) -> DemandBuilder:
        allocation = await cluster.payment_manager.get_allocation()
        return await node_config.market_config.demand.create_demand_builder(
            allocation
        )

    async def _negotiate_initial_proposal(self, request: CreateNodeRequest, demand_builder: DemandBuilder) -> Proposal:
        # TODO MVP: Handle not existing proposal id
        initial_proposal = Proposal(self._golem_node, request.proposal_id)

        negotiating_plugin = NegotiatingPlugin(
            proposal_negotiators=(
                NodeConfigNegotiator(demand_builder),
                PaymentPlatformNegotiator(),
            ),
        )

        demand_data = await initial_proposal.demand.get_demand_data()
        return await negotiating_plugin._negotiate_proposal(demand_data, initial_proposal)

    async def _create_activity(self, proposal: Proposal) -> Activity:
        agreement: Agreement = await proposal.create_agreement()
        await agreement.confirm()
        await agreement.wait_for_approval()
        return await agreement.create_activity()

    def _prepare_sidecars(self, node_config: NodeConfig) -> List[Sidecar]:
        sidecars = []

        for sidecar in node_config.sidecars:
            sidecar_class, sidecar_args, sidecar_kwargs = sidecar.import_object()
            sidecars.append(sidecar_class(*sidecar_args, **sidecar_kwargs))

        return sidecars
