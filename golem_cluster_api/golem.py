import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decimal import Decimal
from golem.managers import DefaultPaymentManager
from golem.managers.base import ProposalNegotiator
from golem.resources import Allocation, AllocationException, DemandData, ProposalData, DemandBuilder
from golem.utils.logging import trace_span
from ya_payment import models

from golem_cluster_api.utils import run_subprocess_output

YAGNA_PATH = Path(os.getenv("YAGNA_PATH", "yagna"))

logger = logging.getLogger(__name__)


class NodeConfigNegotiator(ProposalNegotiator):
    def __init__(self, demand_builder: DemandBuilder) -> None:
        self._demand_builder = demand_builder

    async def __call__(self, demand_data: DemandData, proposal_data: ProposalData) -> None:
        demand_data.properties.update(self._demand_builder.properties)

        if self._demand_builder.constraints not in demand_data.constraints.items:
            demand_data.constraints.items.append(self._demand_builder.constraints)


class NoMatchingPlatform(AllocationException): ...


class DriverListAllocationPaymentManager(DefaultPaymentManager):
    @trace_span(show_arguments=True, show_results=True)
    async def _create_allocation(self, budget: Decimal, network: str, driver: str) -> Allocation:
        output = json.loads(
            await run_subprocess_output(YAGNA_PATH, "payment", "driver", "list", "--json")
        )

        try:
            network_output = output[driver]["networks"][network]
            platform = network_output["tokens"][network_output["default_token"]]
        except KeyError:
            raise NoMatchingPlatform(network, driver)

        timestamp = datetime.now(timezone.utc)
        timeout = timestamp + timedelta(days=365 * 10)

        data = models.Allocation(
            payment_platform=platform,
            total_amount=str(budget),
            timestamp=timestamp,
            timeout=timeout,
            # This will probably be removed one day (consent-related thing)
            make_deposit=False,
            # We must set this here because of the ya_client interface
            allocation_id="",
            spent_amount="",
            remaining_amount="",
        )

        return await Allocation.create(self._golem, data)
