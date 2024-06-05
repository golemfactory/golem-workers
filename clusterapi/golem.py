import asyncio
from typing import List, Tuple

from golem.managers import RefreshingDemandManager
from golem.managers.base import ProposalNegotiator
from golem.payload import Constraints, Properties
from golem.resources import DemandData, Proposal, ProposalData
from ray_on_golem.server.models import NodeConfigData
from ray_on_golem.server.services.golem.helpers import DemandConfigHelper

from clusterapi.exceptions import ProposalPoolException


class ProposalPool:
    def __init__(self, golem, items) -> None:
        self._golem_node = golem
        self._index = 0
        self._items = items

    async def get_proposal(self) -> Proposal:
        idx = self._index
        self._index += 1
        try:
            return Proposal(self._golem_node, id_=self._items[idx])
        except IndexError:
            # TODO How to make this exception not stop entire thing but stop it after all is processed?
            raise ProposalPoolException("Run out of proposals to create the agreement with")


class NodeConfigNegotiator(ProposalNegotiator):
    _config_properties: Tuple[Properties]
    _config_constraints: Tuple[Constraints]

    def __init__(self, node_config: NodeConfigData) -> None:
        self._node_config = node_config
        self._storage = {}

    async def setup(self):
        self._config_properties, self._config_constraints = zip(
            *[
                await payload.build_properties_and_constraints()
                for payload in (
                    await DemandConfigHelper(registry_stats=False).get_payloads_from_demand_config(
                        self._node_config.demand
                    )
                )
            ]
        )

    async def __call__(self, demand_data: DemandData, proposal_data: ProposalData) -> None:
        for config_properties in self._config_properties:
            demand_data.properties.update(config_properties)
        for config_constraints in self._config_constraints:
            if config_constraints not in demand_data.constraints.items:
                demand_data.constraints.items.append(config_constraints)


class ClusterAPIDemandManager(RefreshingDemandManager):
    # TODO crate common manager for this and RefreshingDemandManager and make both inherit from it
    def get_initial_proposals(self) -> List[Proposal]:
        proposals = []
        try:
            while True:
                proposals.append(self._initial_proposals.get_nowait())
        except asyncio.QueueEmpty:
            return proposals
