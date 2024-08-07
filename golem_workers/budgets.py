import logging
from abc import ABC
from datetime import timedelta
from typing import Optional, Sequence, MutableSequence

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

logger = logging.getLogger(__name__)


class Budget(ABC):
    """Base class for budget management."""

    async def start(self):
        """Start the budget and its internal state."""
        ...

    async def stop(self):
        """Stop the budget and cleanup its internal state."""
        ...

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


#     async def register_agreement(self, agreement: Agreement):
#         self._agreements.append(agreement)
#
#     async def unregister_agreement(self, agreement: Agreement):
#         self._agreements.remove(agreement)
#
#     @abstractmethod
#     async def can_node_be_created(self, cluster: Cluster, node: Node) -> bool:
#         ...


class BlankBudget(Budget): ...


class LinearModelBudget(Budget):
    """Budget with basic support of the `linear` price model.

    It makes the demand to match only `linear` pricing models and filter out proposals that exceeds given prices.

    Note that raw time-based prices in proposals are in per-second format - they must be multiplied by `3600` to be used here.
    """

    def __init__(
        self,
        max_initial_price: Optional[float] = None,
        max_duration_hour_price: Optional[float] = None,
        max_cpu_hour_price: Optional[float] = None,
    ) -> None:
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
    """Budget that calculates prices based on average usage of a single cpu.

    This can be helpful to abstract away differences in prices for low or high amount of cpus available in the vms.

    Per cpu average cost is calculated as a sum of:
    - initial_price / cpu_count
    - duration_hour_price * average_duration_hours / cpu_count
    - cpu_hour_price * average_duration_hours * average_cpu_load
    """

    def __init__(
        self,
        average_cpu_load: float,
        average_duration_hours: float,
        average_max_cost: Optional[float] = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

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
# class InitialBudget(Budget):
#     def __init__(self, allocation: Allocation, extra: Dict, extra_key: str = CLUSTER_EXTRA_INITIAL_BUDGET_KEY, budget: Decimal):
#         self._allocation = allocation
#         self._extra = extra
#         self._extra_key = extra_key
#         self._budget = budget
#
#     async def start(self) -> None:
#         if self._extra_key in self._extra:
#             logger.info("Allocation was already amended")
#             return
#
#         await self._allocation.amend(self._budget)
#
#         self._extra[self._extra_key] = True
#
#         logger.info(f"Allocation amended with amount of `{self._budget}`")
#
#     async def stop(self) -> None:
#         pass
#
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
