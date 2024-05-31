import asyncio
from typing import List, Tuple

from golem.managers import RefreshingDemandManager
from golem.managers.base import ProposalNegotiator
from golem.payload import Constraints, Properties
from golem.resources import DemandData, Proposal, ProposalData
from ray_on_golem.server.models import NodeConfigData
from ray_on_golem.server.services.golem.helpers import DemandConfigHelper


class ProposalGenHelper:
    def __init__(self, golem, items) -> None:
        self._golem_node = golem
        self._index = 0
        self._items = items

    async def __call__(self, *args, **kwargs):
        idx = self._index
        self._index += 1
        try:
            print(idx, len(self._items))
            return Proposal(self._golem_node, id_=self._items[idx])
        except IndexError:
            # TODO How to make this exception not stop entire thing but stop it after all is processed?
            raise StopAsyncIteration("Run out of proposals to create the agreement with")


class NodeConfigNegotiator(ProposalNegotiator):
    _config_properties: Tuple[Properties]
    _config_constrains: Tuple[Constraints]

    def __init__(self, node_config: NodeConfigData) -> None:
        self._node_config = node_config

    async def setup(self):
        self._config_properties, self._config_constrains = zip(
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
        """
        Traceback (most recent call last):
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/managers/proposal/plugins/negotiating/negotiating_plugin.py", line 47, in get_proposal
            negotiated_proposal = await self._negotiate_proposal(demand_data, proposal)
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/utils/logging.py", line 234, in _async_wrapper
            result = await func(*args, **kwargs)
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/managers/proposal/plugins/negotiating/negotiating_plugin.py", line 93, in _negotiate_proposal
            demand_proposal = await self._send_demand_proposal(offer_proposal, demand_data)
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/utils/logging.py", line 234, in _async_wrapper
            result = await func(*args, **kwargs)
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/managers/proposal/plugins/negotiating/negotiating_plugin.py", line 113, in _send_demand_proposal
            return await offer_proposal.respond(
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/resources/base.py", line 75, in wrapper
            return await f(*args, **kwargs)
        File "/home/lucjan/Repos/cluster-api/.venv/lib/python3.10/site-packages/golem/resources/proposal/proposal.py", line 167, in respond
            properties=properties.serialize(), constraints=constraints.serialize()
        AttributeError: 'dict' object has no attribute 'serialize'
        """  # TODO add `properties`
        for config_properties in self._config_properties:
            demand_data.properties = {**demand_data.properties, **config_properties}


class ClusterAPIDemandManager(RefreshingDemandManager):
    # TODO crate common manager for this and RefreshingDemandManager and make both inherit from it
    def get_initial_proposals(self) -> List[Proposal]:
        proposals = []
        try:
            while True:
                proposals.append(self._initial_proposals.get_nowait())
        except asyncio.QueueEmpty:
            return proposals
