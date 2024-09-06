import asyncio

from datetime import timedelta
from pydantic import Field
from typing import List, Callable, Optional

from golem.managers import (
    PaymentManager,
    ProposalScoringMixin,
)
from golem.node import GolemNode
from golem.resources import Proposal
from golem_workers.cluster import ManagerStack
from golem_workers.commands.base import Command, CommandRequest, CommandResponse
from golem_workers.models import MarketConfig, ProposalOut, PaymentConfig, ImportableBudget


class GetProposalsRequest(CommandRequest):
    market_config: MarketConfig = Field(
        description="Market configuration to be used for gathering proposals from the market. It's definition can be "
        "partial in comparison with definition in node creation."
    )
    budget: Optional[ImportableBudget] = Field(
        default=ImportableBudget("golem_workers.budgets.BlankBudget"),
        description="Budget to be used for market processing.",
    )
    payment_config: PaymentConfig = Field(
        default_factory=PaymentConfig,
        description="Payment configuration to be used for gathering proposals from the market.",
    )
    collection_time_seconds: float = Field(
        default=5,
        description="Number of seconds of how long proposals should be gathered on the market. Too small value can "
        "result in less or even no proposals.",
    )


class GetProposalsResponse(CommandResponse):
    proposals: List[ProposalOut]


class GetProposalsCommand(Command[GetProposalsRequest, GetProposalsResponse]):
    """Reads proposals from Golem Network based on given `market_config`."""

    def __init__(
        self,
        golem_node: GolemNode,
        temp_payment_manager_factory: Callable[..., PaymentManager],
    ) -> None:
        self._golem_node = golem_node
        self._temp_payment_manager_factory = temp_payment_manager_factory

    async def __call__(self, request: GetProposalsRequest) -> GetProposalsResponse:
        temp_payment_manager = self._temp_payment_manager_factory(
            self._golem_node,
            budget=0,
            network=request.payment_config.network,
            driver=request.payment_config.driver,
        )

        temp_allocation = await temp_payment_manager.get_allocation()
        allow_allocation_amendment = False

        budget_class, budget_args, budget_kwargs = request.budget.import_object()
        budget = budget_class(
            temp_allocation, allow_allocation_amendment, *budget_args, **budget_kwargs
        )

        # TODO: Use offline market scan instead of demand
        simple_manager_stack = await ManagerStack.create_basic_stack(
            self._golem_node,
            request.market_config,
            budget,
        )

        await simple_manager_stack.start()

        proposals = await self._collect_proposals(
            simple_manager_stack, timeout=timedelta(seconds=request.collection_time_seconds)
        )

        # proposal_queue = SimpleBuffer(proposals)
        # await proposal_queue.set_exception(asyncio.QueueEmpty())

        # proposal_manager_plugins = []
        # for filter_definition in request.market_config.filters:
        #     obj, args, kwargs = filter_definition.import_object()
        #
        #     plugin: ProposalManagerPlugin = obj(*args, **kwargs)
        #
        #     proposal_manager_plugins.append(plugin)

        # proposal_manager = DefaultProposalManager(
        #     self._golem_node,
        #     proposal_queue.get,
        #     # plugins=proposal_manager_plugins,
        # )
        #
        # await proposal_manager.start()
        #
        # while True:
        #     try:
        #         proposals.append(
        #             await proposal_manager.get_draft_proposal()  # FIXME: no negotiation in plugins, so we still receive initial proposals
        #         )
        #     except asyncio.QueueEmpty:
        #         break
        #
        # await proposal_manager.stop()

        # if request.market_config.sorters:
        #     sorters: List[ProposalScorer] = []
        #     for sorter_definition in request.market_config.sorters:
        #         obj, args, kwargs = sorter_definition.import_object()
        #         sorters.append(obj(*args, **kwargs))
        #

        scoring = ProposalScoringMixin(await budget.get_pre_negotiation_scorers())

        scored_proposals = await scoring.do_scoring(proposals)

        proposals = [p for _, p in scored_proposals]

        proposals_data = [await o.get_proposal_data() for o in proposals]

        await simple_manager_stack.stop()
        await temp_allocation.release()

        return GetProposalsResponse(
            proposals=[
                ProposalOut(
                    proposal_id=proposal_data.proposal_id,
                    issuer_id=proposal_data.issuer_id,
                    state=proposal_data.state,
                    timestamp=proposal_data.timestamp,
                    properties=proposal_data.properties,
                )
                for proposal_data in proposals_data
            ],
        )

    async def _collect_proposals(
        self, manager_stack: ManagerStack, timeout: timedelta
    ) -> List[Proposal]:
        proposals = []

        proposals_coro = self._collect_proposals_coro(manager_stack, proposals)

        try:
            await asyncio.wait_for(proposals_coro, timeout=timeout.total_seconds())
        except asyncio.TimeoutError:
            pass

        return proposals

    async def _collect_proposals_coro(
        self, manager_stack: ManagerStack, proposals: List[Proposal]
    ) -> None:
        while True:
            proposals.append(await manager_stack.get_draft_proposal())
