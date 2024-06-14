from _decimal import Decimal

import asyncio
import json
import logging
import os
from asyncio.subprocess import Process
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from typing import Optional
from ya_payment import models

from golem.managers import DefaultPaymentManager
from golem.managers.base import ProposalNegotiator
from golem.resources import AllocationException, Allocation, DemandData, ProposalData
from golem.utils.logging import trace_span
from golem_cluster_api.exceptions import ClusterApiError
from golem_cluster_api.models import MarketConfig

YAGNA_PATH = Path(os.getenv("YAGNA_PATH", "yagna"))

logger = logging.getLogger(__name__)


class NodeConfigNegotiator(ProposalNegotiator):
    def __init__(self, market_config: MarketConfig) -> None:
        self._market_config = market_config

    async def __call__(self, demand_data: DemandData, proposal_data: ProposalData) -> None:
        demand_data.properties.update(self._market_config.demand.properties)

        # for config_constraints in self._config_constraints:
        #     if config_constraints not in demand_data.constraints.items:
        #         demand_data.constraints.items.append(config_constraints)


async def run_subprocess(
    *args,
    stderr=asyncio.subprocess.DEVNULL,
    stdout=asyncio.subprocess.DEVNULL,
    detach=False,
) -> Process:
    process = await asyncio.create_subprocess_exec(
        *args,
        stderr=stderr,
        stdout=stdout,
        start_new_session=detach,
    )

    return process


async def run_subprocess_output(*args, timeout: Optional[timedelta] = None) -> bytes:
    process = await run_subprocess(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout.total_seconds() if timeout else None,
        )
    except asyncio.TimeoutError as e:
        if process.returncode is None:
            process.kill()
            await process.wait()

        raise ClusterApiError(f"Process could not finish in timeout of {timeout}!") from e

    if process.returncode != 0:
        raise ClusterApiError(
            f"Process exited with code `{process.returncode}`!\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    return stdout


class NoMatchingPlatform(AllocationException):
    ...


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