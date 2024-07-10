import logging
from typing import Optional, TypeVar, Callable, Awaitable

from golem.managers import (
    AgreementManager,
    DefaultAgreementManager,
    DefaultProposalManager,
    Manager,
    NegotiatingPlugin,
    PaymentPlatformNegotiator,
)
from golem.managers.demand.single_use import SingleUseDemandManager
from golem.node import GolemNode
from golem.resources import Agreement, Allocation
from golem_cluster_api.models import MarketConfig

TManager = TypeVar("TManager", bound=Manager)

logger = logging.getLogger(__name__)


class ManagerStack:
    def __init__(self) -> None:
        self._managers = []
        self._agreement_manager: Optional[AgreementManager] = None

    def add_manager(self, manager: TManager) -> TManager:
        self._managers.append(manager)

        if isinstance(manager, AgreementManager):
            self._agreement_manager = manager

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

    async def get_agreement(self) -> Agreement:
        return await self._agreement_manager.get_agreement()

    @classmethod
    async def create(
        cls,
        golem_node: GolemNode,
        get_allocation: Callable[[], Awaitable[Allocation]],
        market_config: MarketConfig,
    ) -> "ManagerStack":
        stack = cls()

        payloads = await market_config.demand.prepare_payloads()

        demand_manager = stack.add_manager(
            SingleUseDemandManager(
                golem_node,
                get_allocation,
                payloads,
            )
        )

        proposal_manager = stack.add_manager(
            DefaultProposalManager(
                golem_node,
                demand_manager.get_initial_proposal,
                plugins=[
                    NegotiatingPlugin(
                        proposal_negotiators=[
                            PaymentPlatformNegotiator(),
                        ],
                    ),
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
