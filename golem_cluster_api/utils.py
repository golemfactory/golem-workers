import asyncio
from datetime import timedelta
from typing import List

from golem.resources import ProposalData, Demand, Proposal


async def collect_initial_proposals(demand: Demand, timeout: timedelta) -> List[ProposalData]:
    demand.start_collecting_events()

    proposals = []

    proposals_coro = _collect_initial_proposals(demand, proposals)

    try:
        await asyncio.wait_for(proposals_coro, timeout=timeout.total_seconds())
    except asyncio.TimeoutError:
        pass

    # demand.stop_collecting_events()

    return [await o.get_proposal_data() for o in proposals]


async def _collect_initial_proposals(demand: Demand, proposals: List[Proposal]) -> None:
    async for proposal in demand.initial_proposals():
        proposals.append(proposal)
