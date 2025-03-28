from enum import Enum
from golem.payload import Properties
from pydantic import Field
from typing import List, Optional, Callable
from golem.managers import PaymentManager
from golem.node import GolemNode
from golem_workers.commands.base import Command, CommandRequest, CommandResponse
from golem_workers.models import ProposalOut


class PaymentNetwork(str, Enum):
    MAINNET = "mainnet"
    SEPOLIA = "sepolia"
    RINKEBY = "rinkeby"
    GOERLI = "goerli"
    HOLESKY = "holesky"
    POLYGON = "polygon"
    MUMBAI = "mumbai"
    AMOY = "amoy"


class GetProposalsRequest(CommandRequest):
    # New parameters format
    subnet: Optional[str] = Field(
        default=None,
        description="The subnet to use for gathering proposals. Specify a subnet tag to filter providers."
    )
    payment_network: Optional[PaymentNetwork] = Field(
        default=None,
        description="Payment network to use for the proposals. Available networks: mainnet, sepolia, rinkeby, goerli, "
                    "holesky, polygon, mumbai, amoy."
    )
    runtime: Optional[str] = Field(
        default=None,
        description="The runtime environment to use (e.g., 'vm', 'wasm')."
    )
    gpu_model: Optional[str] = Field(
        default=None,
        description="Filter proposals by specific GPU model requirements."
    )
    collection_time_seconds: float = Field(
        default=5,
        description="Number of seconds of how long proposals should be gathered on the market. Too small value can "
                    "result in less or even no proposals.",
    )


class GetProposalsResponse(CommandResponse):
    proposals: List[ProposalOut]


class GetProposalsCommand(Command[GetProposalsRequest, GetProposalsResponse]):
    CONSTRAINTS_DELIMITER = ""

    def __init__(self, golem_node: GolemNode, _temp_payment_manager_factory: Callable[..., PaymentManager],) -> None:
        self._golem_node = golem_node

    async def __call__(self, request: GetProposalsRequest) -> GetProposalsResponse:
        constraints_expression = self._build_constraints_expression(request)

        # Transform offers into ProposalOut format
        proposals = []
        print('constraints_expression:', constraints_expression)

        async for offer_data in self._golem_node.scan(quick_scan=True, constraints=constraints_expression):
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

    def _build_constraints_expression(self, request: GetProposalsRequest) -> Optional[str]:
        constraints = []

        if request.payment_network:
            network = request.payment_network
            token = 'glm' if network in {PaymentNetwork.MAINNET, PaymentNetwork.POLYGON}  else 'tglm'
            constraints.append(f"(golem.com.payment.platform.erc20-{network}-{token}.address=*)")

        if request.subnet:
            constraints.append(f"(golem.node.debug.subnet={request.subnet})")

        if request.runtime:
            constraints.append(f"(golem.runtime.name={request.runtime})")

        if request.gpu_model:
            constraints.append(f"(golem.inf.gpu.d0.model={request.gpu_model})")

        return f"(&{self.CONSTRAINTS_DELIMITER.join(constraints)})" if constraints else None