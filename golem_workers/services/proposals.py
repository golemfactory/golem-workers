import logging
from enum import Enum
from typing import Callable, List, Optional

from golem.managers import PaymentManager
from golem.node import GolemNode
from golem.payload import Properties

from golem_workers.models import ProposalOut
from golem_workers.services.interfaces import IProposalService

# Create a logger for this module
logger = logging.getLogger(__name__)


class PaymentNetwork(str, Enum):
    MAINNET = "mainnet"
    SEPOLIA = "sepolia"
    RINKEBY = "rinkeby"
    GOERLI = "goerli"
    HOLESKY = "holesky"
    POLYGON = "polygon"
    MUMBAI = "mumbai"
    AMOY = "amoy"


class ProposalService(IProposalService):
    """Service for managing proposals."""

    CONSTRAINTS_DELIMITER = ""

    def __init__(
        self,
        golem_node: GolemNode,
        payment_manager_factory: Callable[..., PaymentManager],
    ) -> None:
        self._golem_node = golem_node
        self._payment_manager_factory = payment_manager_factory

    async def get_proposals(self, request_data) -> List[ProposalOut]:
        """Get proposals based on request parameters."""
        constraints_expression = self._build_constraints_expression(request_data)

        # Transform offers into ProposalOut format
        proposals = []
        logger.debug("constraints_expression: %s", constraints_expression)

        async for offer_data in self._golem_node.scan(
            quick_scan=True, constraints=constraints_expression
        ):
            proposals.append(
                ProposalOut(
                    proposal_id=offer_data.offerId,
                    issuer_id=offer_data.providerId,
                    state="Draft",
                    timestamp=offer_data.timestamp,
                    properties=Properties(offer_data.properties),
                )
            )
        return proposals

    def _build_constraints_expression(self, request_data) -> Optional[str]:
        constraints = []

        if hasattr(request_data, "payment_network") and request_data.payment_network:
            network = request_data.payment_network
            token = "glm" if network in {PaymentNetwork.MAINNET, PaymentNetwork.POLYGON} else "tglm"
            constraints.append(f"(golem.com.payment.platform.erc20-{network}-{token}.address=*)")

        if hasattr(request_data, "subnet") and request_data.subnet:
            constraints.append(f"(golem.node.debug.subnet={request_data.subnet})")

        if hasattr(request_data, "runtime") and request_data.runtime:
            constraints.append(f"(golem.runtime.name={request_data.runtime})")

        if hasattr(request_data, "gpu_model") and request_data.gpu_model:
            constraints.append(f"(golem.inf.gpu.d0.model={request_data.gpu_model})")

        return f"(&{self.CONSTRAINTS_DELIMITER.join(constraints)})" if constraints else None
