import logging
from datetime import timedelta
from typing import Optional, TypeVar, Callable, Awaitable

from golem.managers import (
    AgreementManager,
    DefaultAgreementManager,
    DefaultProposalManager,
    Manager,
    NegotiatingPlugin,
    PaymentPlatformNegotiator,
    ProposalScoringBuffer,
    DemandManager,
    ProposalManager,
)
from golem.managers.demand.single_use import SingleUseDemandManager
from golem.node import GolemNode
from golem.resources import Agreement, Allocation, Proposal
from golem_workers.budgets import Budget
from golem_workers.models import MarketConfig

TManager = TypeVar("TManager", bound=Manager)

logger = logging.getLogger(__name__)


class ManagerStack:
    def __init__(self) -> None:
        self._managers = []
        self._agreement_manager: Optional[AgreementManager] = None
        self._proposal_manager: Optional[ProposalManager] = None

    def add_manager(self, manager: TManager) -> TManager:
        self._managers.append(manager)

        if isinstance(manager, AgreementManager):
            self._agreement_manager = manager

        if isinstance(manager, ProposalManager):
            self._proposal_manager = manager

        return manager

    async def start(self) -> None:
        logger.info("Starting stack managers...")

        for manager in self._managers:
            if manager is not None:
                await manager.start()

        logger.info("Starting stack managers done")

    async def stop(self) -> None:
        logger.info("Stopping stack managers...")

        for manager in reversed(self._managers):
            if manager is not None:
                try:
                    await manager.stop()
                except Exception:
                    logger.exception(f"{manager} stop failed!")

        logger.info("Stopping stack managers done")

    async def get_draft_proposal(self) -> Proposal:
        return await self._proposal_manager.get_draft_proposal()

    async def get_agreement(self) -> Agreement:
        return await self._agreement_manager.get_agreement()

    @classmethod
    async def _create_demand_manager(
        cls,
        golem_node: GolemNode,
        get_allocation: Callable[[], Awaitable[Allocation]],
        market_config: MarketConfig,
        budget: Budget,
    ) -> DemandManager:
        payloads = list(await market_config.demand.prepare_payloads())
        payloads.extend(await budget.get_payloads())

        return SingleUseDemandManager(
            golem_node,
            get_allocation,
            payloads,
        )

    @classmethod
    async def create_basic_stack(
        cls,
        golem_node: GolemNode,
        get_allocation: Callable[[], Awaitable[Allocation]],
        market_config: MarketConfig,
        budget: Budget,
    ) -> "ManagerStack":
        stack = cls()

        demand_manager = stack.add_manager(
            await cls._create_demand_manager(golem_node, get_allocation, market_config, budget)
        )

        stack.add_manager(
            DefaultProposalManager(
                golem_node,
                demand_manager.get_initial_proposal,
                plugins=[
                    *(await budget.get_pre_negotiation_plugins()),
                ],
            )
        )

        return stack

    @classmethod
    async def create_agreement_stack(
        cls,
        golem_node: GolemNode,
        get_allocation: Callable[[], Awaitable[Allocation]],
        market_config: MarketConfig,
        budget: Budget,
    ) -> "ManagerStack":
        stack = cls()

        demand_manager = stack.add_manager(
            await cls._create_demand_manager(golem_node, get_allocation, market_config, budget)
        )

        proposal_manager = stack.add_manager(
            DefaultProposalManager(
                golem_node,
                demand_manager.get_initial_proposal,
                plugins=[
                    *(await budget.get_pre_negotiation_plugins()),
                    ProposalScoringBuffer(
                        min_size=50,
                        max_size=1000,
                        fill_at_start=True,
                        proposal_scorers=(*(await budget.get_pre_negotiation_scorers()),),
                        scoring_debounce=timedelta(seconds=10),
                    ),
                    NegotiatingPlugin(
                        proposal_negotiators=[
                            PaymentPlatformNegotiator(),
                        ],
                    ),
                    *(await budget.get_post_negotiation_plugins()),
                ],
            )
        )

        stack.add_manager(
            DefaultAgreementManager(
                golem_node,
                proposal_manager.get_draft_proposal,
            )
        )

        return stack
