import importlib

import asyncio

from datetime import timedelta
from typing import List

from golem.node import GolemNode
from golem.payload import defaults as payload_defaults, Payload, Constraints, Properties
from golem.payload.defaults import DEFAULT_SUBNET
from golem.resources import ProposalData, Demand, DemandBuilder, Allocation, Proposal
from golem_cluster_api.models import MarketConfigDemand


async def prepare_demand(golem_node: GolemNode, allocation: Allocation, demand_config: MarketConfigDemand) -> Demand:
    demand_builder = DemandBuilder()

    all_payloads = [
        payload_defaults.ActivityInfo(
            lifetime=payload_defaults.DEFAULT_LIFETIME,
            multi_activity=True
        ),
        payload_defaults.PaymentInfo(),
        await allocation.get_demand_spec(),
    ]

    for payload_dotted_path, payload_data in demand_config.payloads.items():
        module_path, class_name = payload_dotted_path.rsplit('.', 1)
        payload_class = getattr(importlib.import_module(module_path), class_name)

        all_payloads.append(payload_class(**payload_data))

    for demand_spec in all_payloads:
        await demand_builder.add(demand_spec)

    demand_builder.add_properties(Properties(demand_config.properties))

    demand = await demand_builder.create_demand(golem_node)

    await demand.get_data()

    return demand


async def collect_initial_proposals(demand: Demand, timeout: timedelta) -> List[ProposalData]:
    demand.start_collecting_events()

    proposals = []

    proposals_coro = _collect_initial_proposals(demand, proposals)

    try:
        await asyncio.wait_for(proposals_coro, timeout=timeout.total_seconds())
    except asyncio.TimeoutError:
        pass

    demand.stop_collecting_events()

    return [await o.get_proposal_data() for o in proposals]


async def _collect_initial_proposals(demand: Demand, proposals: List[Proposal]) -> None:
    async for proposal in demand.initial_proposals():
        proposals.append(proposal)
