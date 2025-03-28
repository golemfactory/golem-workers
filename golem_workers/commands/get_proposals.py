from golem.managers import PaymentManager
from golem.payload import Properties
from pydantic import Field
from typing import List, Optional, Callable
from golem.node import GolemNode
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
    """Reads proposals from Golem Network based on given `market_config` using offline market scanning."""

    def __init__(self, golem_node: GolemNode, _temp_payment_manager_factory: Callable[..., PaymentManager],) -> None:
        self._golem_node = golem_node

    async def __call__(self, request: GetProposalsRequest) -> GetProposalsResponse:
        # Transform offers into ProposalOut format
        proposals = []
        async for offer_data in self._golem_node.scan(quick_scan=True):
            proposals.append(
                ProposalOut(
                    proposal_id=offer_data.offerId,
                    issuer_id=offer_data.providerId,
                    state="Draft",
                    timestamp=offer_data.timestamp,
                    properties=Properties(offer_data.properties),
                )
            )

        return GetProposalsResponse(proposals=proposals)
