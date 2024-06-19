import importlib

import asyncio
from datetime import timedelta
from pydantic import TypeAdapter, ValidationError
from typing import List, TypeVar

from golem.resources import Demand, Proposal, ProposalData


TImportType = TypeVar("TImportType")


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


def import_from_dotted_path(dotted_path: str, import_type: TImportType) -> TImportType:
    module_path, func_name = dotted_path.rsplit(".", 1)
    imported = getattr(importlib.import_module(module_path), func_name)

    adapter = TypeAdapter(import_type)

    try:
        adapter.validate_python(imported)
    except ValidationError as e:
        raise RuntimeError(
            f"Given python dotted path does not point to `{import_type}` type!"
        ) from e

    return imported
