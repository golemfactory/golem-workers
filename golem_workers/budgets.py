import asyncio

import logging
from abc import ABC
from datetime import timedelta
from typing import Optional, Sequence, MutableSequence, Dict

from golem.managers import (
    ProposalManagerPlugin,
    RejectIfCostsExceeds,
    LinearCoeffsCost,
    LinearPerCpuAverageCostPricing,
    ProposalScorer,
    MapScore,
)
from golem.payload import Payload, GenericPayload, Properties, Constraints
from golem.payload.defaults import PROP_PRICING_MODEL
from golem.resources import Agreement, Allocation, NewInvoice, DebitNote, NewDebitNote
from golem.resources.utils.payment import eth_decimal

logger = logging.getLogger(__name__)

SHUTDOWN_TIMEOUT = timedelta(minutes=2, seconds=30)


class Budget(ABC):
    """Base class for budget management.

    The budget takes care of the way costs are approached.
    Its job is to check the contents of the Proposals, determine how the provider will charge for the usage, and manage your spending according to your preferences via assigned Allocation.

    Args:
        allocation: Externally provided Allocation that DebitNotes and Invoices will be paid from.
        allow_allocation_amendment: Externally provided value for Allocation amendment.
            If True, budget can extend Allocation values, for e.g. with amounts from received DebitNotes/Invoices.
            Useful for service-like use-cases or when there is no known hard limit of spending.
            If False, budget will not amend given Allocation.
            Useful for externally managed Allocations.
        shutdown_timeout: How long the budget should wait for invoices before stopping.
    """

    def __init__(
        self,
        allocation: Allocation,
        allow_allocation_amendment: bool,
        shutdown_timeout: timedelta = SHUTDOWN_TIMEOUT,
    ) -> None:
        self._allocation = allocation
        self._allow_allocation_amendment = allow_allocation_amendment
        self._shutdown_timeout = shutdown_timeout

        self._agreements: Dict[str, Agreement] = {}
        self._agreements_debit_note_event_bus_handlers = {}
        self._agreements_invoice_event_bus_handlers = {}
        self._no_agreements_event = asyncio.Event()

    async def start(self):
        """Start the budget and its internal state."""

        logger.info("Starting budget `%s`...", self)

        logger.info("Starting budget `%s` done", self)

    async def stop(self):
        """Stop the budget and cleanup its internal state."""

        logger.info("Stopping budget `%s`...", self)

        if not self._agreements:
            return

        logger.info("Waiting for invoices up to `%s`...", self._shutdown_timeout)

        try:
            await asyncio.wait_for(
                self._no_agreements_event.wait(), timeout=self._shutdown_timeout.total_seconds()
            )
        except asyncio.TimeoutError:
            agreements = list(self._agreements.values())

            logger.error(
                "Waiting for invoices failed with timeout! Those agreements did not sent invoices:"
                f" {agreements}"
            )

            for agreement in agreements:
                await self.unregister_agreement(agreement)

            self._agreements.clear()
        else:
            logger.info("Waiting for invoices done, all paid")

        logger.info("Stopping budget `%s` done", self)

    async def get_allocation(self) -> Allocation:
        """Return used Allocation."""
        return self._allocation

    async def get_payloads(self) -> Sequence[Payload]:
        """Return the budget contribution to the demand."""
        return []

    async def get_pre_negotiation_plugins(self) -> Sequence[ProposalManagerPlugin]:
        """Return the budget contribution to the proposal processing before proposal negotiations with the provider."""
        return []

    async def get_post_negotiation_plugins(self) -> Sequence[ProposalManagerPlugin]:
        """Return the budget contribution to the proposal processing after proposal negotiations with the provider."""
        return []

    async def get_pre_negotiation_scorers(self) -> Sequence[ProposalScorer]:
        """Return the budget contribution to the proposal scoring before proposal negotiations with the provider."""
        return []

    async def register_agreement(self, agreement: Agreement):
        """Add agreement to collection and track related Invoices / DebitNotes."""
        self._agreements[agreement.id] = agreement

        self._agreements_invoice_event_bus_handlers[
            agreement.id
        ] = await agreement.node.event_bus.on(
            NewInvoice,
            self._on_new_invoice,
        )
        self._agreements_debit_note_event_bus_handlers[
            agreement.id
        ] = await agreement.node.event_bus.on(
            NewDebitNote,
            self._on_new_debit_node,
        )

        self._no_agreements_event.clear()

        logger.info("Agreement `%s` registered to budget `%s`", agreement, self)

    async def unregister_agreement(self, agreement: Agreement):
        """Remove agreement from collection and disable tracking related Invoices / DebitNotes."""

        del self._agreements[agreement.id]

        await agreement.node.event_bus.off(
            self._agreements_invoice_event_bus_handlers[agreement.id]
        )
        del self._agreements_invoice_event_bus_handlers[agreement.id]

        await agreement.node.event_bus.off(
            self._agreements_debit_note_event_bus_handlers[agreement.id]
        )
        del self._agreements_debit_note_event_bus_handlers[agreement.id]

        if not self._agreements:
            self._no_agreements_event.set()

        logger.info("Agreement `%s` unregistered from budget `%s`", agreement, self)

    async def _on_new_invoice(self, event: NewInvoice) -> None:
        breakpoint()
        invoice = event.resource
        invoice_data = await invoice.get_data()

        if self._allow_allocation_amendment:
            await self._amend_allocation_for_amount(invoice_data.amount)

        logger.debug("Accepting invoice `%s`: %s", invoice, invoice_data)

        await invoice.validate_and_accept(
            self._allocation
        )  # TODO: Move validation from Invoice to Budget
        await self.unregister_agreement(self._agreements[invoice_data.agreement_id])

    async def _on_new_debit_node(self, event: NewDebitNote) -> None:
        debit_note: DebitNote = event.resource
        debit_note_data = await debit_note.get_data()

        if self._allow_allocation_amendment:
            # FIXME: Allocation should not be over-amended with growing value value from debitnote
            await self._amend_allocation_for_amount(debit_note_data.total_amount_due)

        logger.debug("Accepting debit note `%s`: %s", debit_note, debit_note_data)
        await debit_note.validate_and_accept(self._allocation)

    async def _amend_allocation_for_amount(self, amount: str) -> None:
        logger.info("Amending allocation `%s` with extra `%s`", self._allocation, amount)

        api = self._allocation._get_api(self._allocation.node)

        allocation_data = await self._allocation.get_data()
        allocation_data.total_amount = str(
            eth_decimal(allocation_data.total_amount) + eth_decimal(amount)
        )
        await api.amend_allocation(self._allocation.id, allocation_data)
        await self._allocation.get_data(True)


#     @abstractmethod
#     async def can_node_be_created(self, cluster: Cluster, node: Node) -> bool:
#         ...


class BlankBudget(Budget): ...


class LinearModelBudget(Budget):
    """Budget with basic support of the `linear` price model.

    It makes the demand to match only `linear` pricing models and filter out proposals that exceed given max prices.

    Args:
        allocation: Externally provided Allocation that DebitNotes and Invoices will be paid from.
        allow_allocation_amendment: Externally provided value for Allocation amendment.
            If True, budget can extend Allocation values, for e.g. with amounts from received DebitNotes/Invoices.
            Useful for service-like use-cases or when there is no known hard limit of spending.
            If False, budget will not amend given Allocation.
            Useful for externally managed Allocations.
        shutdown_timeout: How long the budget should wait for invoices before stopping.

    Keyword Args:
        max_initial_price: Amount that will be flat-charged at the start
        max_duration_hour_price:
            Amount that will be charged for real time.
            Note:
                This price in raw proposal is in per-second format - is must be multiplied by `3600` to be used here as per-hour format.
        max_cpu_hour_price:
            Amount that will be charged for 100% usage of a single CPU core.
            This price will be charged for each available CPU.
            Note:
                This price in raw proposal is in per-second format - is must be multiplied by `3600` to be used here as per-hour format.
    """

    def __init__(
        self,
        allocation: Allocation,
        allow_allocation_amendment: bool,
        shutdown_timeout: timedelta = SHUTDOWN_TIMEOUT,
        *,
        max_initial_price: Optional[float] = None,
        max_duration_hour_price: Optional[float] = None,
        max_cpu_hour_price: Optional[float] = None,
    ) -> None:
        super().__init__(allocation, allow_allocation_amendment, shutdown_timeout)

        self._max_initial_price = max_initial_price
        self._max_duration_price = (
            max_duration_hour_price / 3600 if max_duration_hour_price is not None else None
        )
        self._max_cpu_price = max_cpu_hour_price / 3600 if max_cpu_hour_price is not None else None

    async def get_payloads(self) -> Sequence[Payload]:
        return [
            GenericPayload(
                properties=Properties({PROP_PRICING_MODEL: "linear"}),
                constraints=Constraints(),
            )
        ]

    async def get_pre_negotiation_plugins(self) -> Sequence[ProposalManagerPlugin]:
        plugins = []

        # TODO: Optionally reject proposals with unknown and non-zero coeffs

        self._append_coeff_proposal_manager_plugin(
            plugins, self._max_initial_price, "price_initial"
        )
        self._append_coeff_proposal_manager_plugin(
            plugins, self._max_duration_price, "price_duration_sec"
        )
        self._append_coeff_proposal_manager_plugin(plugins, self._max_cpu_price, "price_cpu_sec")

        return plugins

    @staticmethod
    def _append_coeff_proposal_manager_plugin(
        plugins: MutableSequence[ProposalManagerPlugin], vector_value: Optional[float], coeff: str
    ) -> None:
        if vector_value is not None:
            plugins.append(RejectIfCostsExceeds(vector_value, LinearCoeffsCost(coeff)))


class AveragePerCpuUsageLinearModelBudget(LinearModelBudget):
    """Budget that calculates prices based on the average usage of a single CPU.

    This can be helpful to abstract away differences in prices for low or high amounts of CPUs available on the provider.

    Per CPU average cost is calculated as a sum of:
    - initial_price / cpu_count
    - duration_hour_price * average_duration_hours / cpu_count
    - cpu_hour_price * average_duration_hours * average_cpu_load

    Args:
        allocation: Externally provided Allocation that DebitNotes and Invoices will be paid from.
        allow_allocation_amendment: Externally provided value for Allocation amendment.
            If True, budget can extend Allocation values, for e.g. with amounts from received DebitNotes/Invoices.
            Useful for service-like use-cases or when there is no known hard limit of spending.
            If False, budget will not amend given Allocation.
            Useful for externally managed Allocations.
        shutdown_timeout: How long the budget should wait for invoices before stopping.

    Keyword Args:
        max_initial_price: Amount that will be flat-charged at the start
        max_duration_hour_price:
            Amount that will be charged for real time.
            Note:
                This price in raw proposal is in per-second format - is must be multiplied by `3600` to be used here as per-hour format.
        max_cpu_hour_price:
            Amount that will be charged for 100% usage of a single CPU core.
            This price will be charged for each available CPU.
            Note:
                This price in raw proposal is in per-second format - is must be multiplied by `3600` to be used here as per-hour format.
        average_cpu_load: Normalized float (0.0 - 1.0) of expected use of a single CPU core for a `average_duration_hours` time.
        average_duration_hours: Expected duration of usage that costs will be calculated for.
        average_max_cost: Expected max cost for a single CPU for a `average_duration_hours` time.
    """

    def __init__(
        self,
        allocation: Allocation,
        allow_allocation_amendment: bool,
        shutdown_timeout: timedelta = SHUTDOWN_TIMEOUT,
        *,
        average_cpu_load: float,
        average_duration_hours: float,
        average_max_cost: Optional[float] = None,
        **kwargs,
    ) -> None:
        super().__init__(allocation, allow_allocation_amendment, shutdown_timeout, **kwargs)

        self._average_cpu_load = average_cpu_load
        self._average_duration = average_duration_hours / 3600
        self._average_max_cost = average_max_cost

        self._linear_per_cpu_average_cost = LinearPerCpuAverageCostPricing(
            average_cpu_load=self._average_cpu_load,
            average_duration=timedelta(seconds=self._average_duration),
        )

    async def get_pre_negotiation_plugins(self) -> Sequence[ProposalManagerPlugin]:
        plugins = list(await super().get_pre_negotiation_plugins())

        if self._average_max_cost is not None:
            plugins.append(
                RejectIfCostsExceeds(self._average_max_cost, self._linear_per_cpu_average_cost),
            )

        return plugins

    async def get_pre_negotiation_scorers(self) -> Sequence[ProposalScorer]:
        scorers = list(await super().get_pre_negotiation_scorers())

        scorers.append(
            MapScore(self._linear_per_cpu_average_cost, normalize=True, normalize_flip=True)
        )

        return scorers


#
# CLUSTER_EXTRA_INITIAL_BUDGET_KEY = "initial_budget"
#
# CLUSTER_EXTRA_PER_HOUR_BUDGET_KEY = "per_hour_budget"
#
#
# class PerHourBudget(Budget):
#     def __init__(self, allocation: Allocation, extra: Dict, extra_key: str = CLUSTER_EXTRA_PER_HOUR_BUDGET_KEY, budget: Decimal, pricing_function: PricingCallable) -> None:
#         self._allocation = allocation
#         self._extra = extra
#         self._extra_key = extra_key
#         self._budget = budget
#         self._pricing_function = pricing_function
#
#         self._background_task: Optional[asyncio.Task] = None
#
#     async def start(self) -> None:
#         self._background_task = create_task_with_logging(
#             self._background_loop(),
#             trace_id=get_trace_id_name(self, "background_task")
#         )
#
#         logger.info(f"{self.__class__.__name__} started")
#
#     async def stop(self) -> None:
#         if self._background_task:
#             await ensure_cancelled(self._background_task)
#
#         logger.info(f"{self.__class__.__name__} stopped")
#
#     async def _background_loop(self) -> None:
#         while True:
#             now = datetime.now()
#             previous_amend_at = self._extra.get(self._extra_key, now)
#
#             if previous_amend_at + timedelta(hours=1) < now:
#                 interval = (now - previous_amend_at) + timedelta(hours=1)
#
#                 logger.info(f'Allocation will be amended in `{interval}`')
#
#                 await asyncio.sleep(interval.total_seconds())
#                 continue
#
#             await self._allocation.amend(self._budget)
#
#             self._extra[self._extra_key] = datetime.utcnow()
#
#             logger.info(f"Allocation amended with amount of `{self._budget}`")
#
#     async def can_node_be_created(self, cluster: Cluster, node: Node) -> bool:
#         cluster_current_usage = sum(filter(self._pricing_function(node.agreement_data) for node in cluster.nodes))
#
#         node_usage = self._pricing_function(node.agreement_data)
#
#         return node_usage is not None and cluster_current_usage + node_usage <= self._budget
