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

from golem.managers import DefaultPaymentManager
from golem.resources import AllocationException, Allocation
from golem.utils.logging import trace_span
from golem_cluster_api.exceptions import ClusterApiError
from ya_payment import models

YAGNA_PATH = Path(os.getenv("YAGNA_PATH", "yagna"))

logger = logging.getLogger(__name__)


#
# class ClusterAIPCluster(Cluster):
#     # TODO refactor ray_on_golem `Cluster`
#     def __init__(
#         self,
#         golem_service: GolemService,
#         webserver_port: int,
#         name: str,
#         provider_parameters: ClusterParametersData,
#         on_stop: Optional[Callable[["Cluster"], MaybeAwaitable[None]]] = None,
#     ) -> None:
#         super(Cluster, self).__init__()
#
#         self._golem_service = golem_service
#         self._name = name
#         self._provider_parameters = provider_parameters
#         self._webserver_port = webserver_port
#         self._on_stop = on_stop
#
#         # self._manager_stacks: Dict[StackHash, ManagerStack] = {}
#         # self._manager_stacks_locks: DefaultDict[StackHash, asyncio.Semaphore] = defaultdict(
#         #     asyncio.Semaphore
#         # )
#         self._nodes: Dict[NodeId, ClusterNode] = {}
#         self._nodes_id_counter = 0
#
#         self._state: NodeState = NodeState.terminated
#
#     async def start(self) -> None:
#         """Start the cluster and its internal state."""
#
#         if self._state in (NodeState.pending, NodeState.running):
#             logger.info("Not starting `%s` cluster as it's already running or starting", self)
#             return
#
#         logger.info("Starting `%s` cluster...", self)
#
#         self._state = NodeState.pending
#
#         # await self._payment_manager.start()
#
#         self._state = NodeState.running
#
#         logger.info("Starting `%s` cluster done", self)
#
#     async def stop(self, call_events: bool = True) -> None:
#         """Stop the cluster."""
#
#         if self._state in (NodeState.terminating, NodeState.terminated):
#             logger.info("Not stopping `%s` cluster as it's already stopped or stopping", self)
#             return
#
#         logger.info("Stopping `%s` cluster...", self)
#
#         self._state = NodeState.terminating
#
#         await asyncio.gather(*[node.stop(call_events=False) for node in self._nodes.values()])
#
#         # await asyncio.gather(*[stack.stop() for stack in self._manager_stacks.values()])
#
#         # await self._payment_manager.stop()
#
#         self._state = NodeState.terminated
#         self._nodes.clear()
#         self._nodes_id_counter = 0
#         # self._manager_stacks.clear()
#         # self._manager_stacks_locks.clear()
#
#         if self._on_stop and call_events:
#             create_task_with_logging(
#                 resolve_maybe_awaitable(self._on_stop(self)),
#                 trace_id=get_trace_id_name(self, "on-stop"),
#             )
#
#         logger.info("Stopping `%s` cluster done", self)
#
#     async def request_nodes(
#         self,
#         node_config: NodeConfigData,
#         count: int,
#         tags: Tags,
#         get_agreement,
#     ) -> Iterable[NodeId]:
#         """Create new nodes and schedule their start."""
#
#         is_head_node = utils.is_head_node(tags)
#         worker_type = "head" if is_head_node else "worker"
#         node_type = self._get_node_type(tags)
#
#         logger.info(
#             "Requesting `%s` %s node(s) of type `%s`...",
#             count,
#             worker_type,
#             node_type,
#         )
#
#         # manager_stack, priority_manager_stack = await self._prepare_manager_stacks(node_config)
#         cluster_node_class = ClusterAIPNode
#
#         created_node_ids = []
#         for _ in range(count):
#             node_id = self._get_new_node_id()
#             created_node_ids.append(node_id)
#
#             self._nodes[node_id] = node = cluster_node_class(
#                 get_agreement=get_agreement,
#                 cluster=self,
#                 golem_service=self._golem_service,
#                 priority_agreement_timeout=RAY_ON_GOLEM_PRIORITY_AGREEMENT_TIMEOUT,
#                 on_stop=self._on_node_stop,
#                 node_id=node_id,
#                 tags=tags,
#                 node_config=node_config,
#                 ssh_private_key_path=self._provider_parameters.ssh_private_key,
#                 ssh_public_key_path=self._provider_parameters.ssh_private_key,  # .with_suffix(".pub"),
#                 ssh_user=self._provider_parameters.ssh_user,
#                 manager_stack=None,
#                 priority_manager_stack=None,
#             )
#
#             node.schedule_start()
#
#         logger.info(
#             "Requesting `%s` %s node(s) of type `%s` done",
#             count,
#             worker_type,
#             node_type,
#         )
#         logger.debug(f"{node_config=}")
#
#         return created_node_ids
#
#
# class ClusterAIPNode(ClusterNode):
#     __get_priority_agreement: Any
#     __get_agreement: Any
#
#     # TODO refactor ray_on_golem `ClusterNode`
#     def __init__(
#         self,
#         get_agreement,
#         get_priority_agreement=None,
#         **kwargs,
#     ) -> None:
#         super().__init__(**kwargs)
#         self.__get_priority_agreement = get_priority_agreement
#         self.__get_agreement = get_agreement
#
#     async def _get_agreement(self) -> Agreement:
#         if self.__get_priority_agreement:
#             try:
#                 return await asyncio.wait_for(
#                     self.__get_priority_agreement(),
#                     timeout=self._priority_agreement_timeout.total_seconds(),
#                 )
#             except asyncio.TimeoutError:
#                 self._add_state_log(
#                     "No recommended providers were found. We are extending the search to all "
#                     "public providers, which might be less stable. Restart the cluster to try "
#                     "finding recommended providers again. If the problem persists please let us "
#                     "know at `#Ray on Golem` discord channel (https://chat.golem.network/)"
#                 )
#
#         return await self.__get_agreement()
#
#
# class ProposalPool:
#     def __init__(self, golem, items) -> None:
#         self._golem_node = golem
#         self._index = 0
#         self._items = items
#
#     async def get_proposal(self) -> Proposal:
#         idx = self._index
#         self._index += 1
#         try:
#             return Proposal(self._golem_node, id_=self._items[idx])
#         except IndexError:
#             # TODO How to make this exception not stop entire thing but stop it after all is processed?
#             raise ProposalPoolException("Run out of proposals to create the agreement with")
#
#
# class NodeConfigNegotiator(ProposalNegotiator):
#     _config_properties: Tuple[Properties]
#     _config_constraints: Tuple[Constraints]
#
#     def __init__(self, node_config: NodeConfigData) -> None:
#         self._node_config = node_config
#         self._storage = {}
#
#     async def setup(self):
#         self._config_properties, self._config_constraints = zip(
#             *[
#                 await payload.build_properties_and_constraints()
#                 for payload in (
#                     await DemandConfigHelper(registry_stats=False).get_payloads_from_demand_config(
#                         self._node_config.demand
#                     )
#                 )
#             ]
#         )
#
#     async def __call__(self, demand_data: DemandData, proposal_data: ProposalData) -> None:
#         for config_properties in self._config_properties:
#             demand_data.properties.update(config_properties)
#         for config_constraints in self._config_constraints:
#             if config_constraints not in demand_data.constraints.items:
#                 demand_data.constraints.items.append(config_constraints)
#
#
# class ClusterAPIDemandManager(RefreshingDemandManager):
#     # TODO crate common manager for this and RefreshingDemandManager and make both inherit from it
#     def get_initial_proposals(self) -> List[Proposal]:
#         proposals = []
#         try:
#             while True:
#                 proposals.append(self._initial_proposals.get_nowait())
#         except asyncio.QueueEmpty:
#             return proposals


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
