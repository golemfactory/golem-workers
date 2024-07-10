import logging
from abc import ABC

# from golem_cluster_api.cluster import Cluster, Node

logger = logging.getLogger(__name__)


class Budget(ABC):
    def __init__(self):
        self._agreements = []

    async def start(self):
        pass

    async def stop(self):
        pass


#     async def register_agreement(self, agreement: Agreement):
#         self._agreements.append(agreement)
#
#     async def unregister_agreement(self, agreement: Agreement):
#         self._agreements.remove(agreement)
#
#     @abstractmethod
#     async def can_node_be_created(self, cluster: Cluster, node: Node) -> bool:
#         ...
#
#     async def filter_proposal(self):
#         ...
#
#     async def sort_proposal(self):
#         ...

#
# class LinearModelBudget(Budget):
#     def __init__(self, coefs: Dict[str, Callable[[Properties], Optional[float]]]) -> None:
#         self._coefs = coefs
#
#     def _calculate_price(self, properties: Properties) -> float:
#
#         ...
#
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
