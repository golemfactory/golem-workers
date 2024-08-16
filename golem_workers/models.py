from abc import ABC
import collections.abc

from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Union, Tuple, Sequence

import dpath
from typing_extensions import Annotated

from golem.payload import PayloadSyntaxParser, Properties, Payload, GenericPayload, Constraints
from golem.resources import ProposalId
from golem.resources.proposal.data import ProposalState
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, RootModel, model_validator

from golem_workers.utils import import_from_dotted_path

if TYPE_CHECKING:
    from golem_workers.cluster.cluster import Cluster
    from golem_workers.cluster.node import Node


class RequestBaseModel(BaseModel, ABC):
    model_config = ConfigDict(extra="forbid")


class ResponseBaseModel(BaseModel, ABC):
    model_config = ConfigDict(extra="ignore")


class ClusterState(Enum):
    """Enum related to cluster state."""

    CREATED = "created"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DELETING = "deleting"


class NodeState(Enum):
    """Enum related to node state."""

    CREATED = "created"
    PROVISIONING = "provisioning"
    PROVISIONING_FAILED = "provisioning-failed"
    PROVISIONED = "provisioned"
    STARTING = "starting"
    STARTING_FAILED = "starting-failed"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DELETING = "deleting"


# TODO POC: extend https://docs.pydantic.dev/latest/api/types/#pydantic.types.ImportString
class ImportableElement(RootModel):
    root: Union[
        Annotated[
            str,
            Field(
                description="Importable dotted path to Python object. Shortcut for objects with no arguments or all-default arguments."
            ),
        ],
        Annotated[
            Mapping[
                str,
                Union[
                    Annotated[
                        Mapping,
                        Field(
                            description="Collection of kwargs to be applied for importable object."
                        ),
                    ],
                    Annotated[
                        Sequence,
                        Field(
                            description="Collection of args to be applied for importable object."
                        ),
                    ],
                ],
            ],
            Field(
                min_length=1,
                max_length=1,
                description="Object which the only key is a importable dotted path to Python object.",
            ),
        ],
    ]

    @model_validator(mode="after")
    def validate_importable_element(self):
        try:
            self.import_object()
        except ImportError as e:
            raise ValueError("Given dotted path is not importable!") from e

        # TODO: deep inspection of arguments without calling imported_object
        #  supported in pydantic by @validate_call, but in v1.10+ there is no easy way to run
        #  validation only

        return self

    def import_object(self) -> Tuple[Any, Sequence, Mapping]:
        if isinstance(self.root, str):
            path = self.root
            data = []  # empty positional args
        else:
            path = next(iter(self.root))
            data = self.root[path]

        imported_object = import_from_dotted_path(path)

        if isinstance(data, collections.abc.Sequence):
            args = data
            kwargs = {}
        else:
            args = []
            kwargs = data

        return imported_object, args, kwargs


ImportableBudget = ImportableElement
ImportablePayload = ImportableElement
ImportableFilter = ImportableElement
ImportableSorter = ImportableElement
ImportableSidecar = ImportableElement
ImportableContext = ImportableElement
ImportableWorkFunc = ImportableElement


class BudgetScope(Enum):
    # GLOBAL = "global"
    CLUSTER = "cluster"
    NODE_TYPE = "node-type"
    NODE = "node"


class BudgetConfig(BaseModel):
    budget: ImportableBudget
    scope: BudgetScope = BudgetScope.NODE


class MarketConfigDemand(BaseModel):
    """Collection of highly customisable payload objects, properties and constraints to be applied to the demand."""

    model_config = ConfigDict(extra="forbid")

    payloads: List[ImportablePayload] = Field(
        default_factory=list,
        description="List of importable payloads to be added to the demand exactly in given order.",
    )
    properties: Mapping[str, Any] = Field(
        default_factory=dict,
        description="Collection of raw properties to be added to the demand on top of payloads.",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="List of [raw constraints](https://github.com/golemfactory/golem-architecture/pull/83) to be added to the demand on top of payloads.",
    )

    async def prepare_payloads(self) -> Sequence[Payload]:
        payloads = []

        for payload in self.payloads:
            payload_class, payload_args, payload_kwargs = payload.import_object()

            payloads.append(payload_class(*payload_args, **payload_kwargs))

        # TODO MVP: move Properties creation to object parsing?
        # TODO MVP: move Constraints creation to object parsing?
        payloads.append(
            GenericPayload(
                properties=Properties(self.properties),
                constraints=PayloadSyntaxParser.get_instance().parse_constraints(
                    "(& {})".format(
                        " ".join(c if c.startswith("(") else f"({c})" for c in self.constraints)
                    )
                )
                or Constraints(),
            )
        )

        return payloads


class NetworkConfig(BaseModel):
    """Definition of the way how to prepare VPN networks."""

    model_config = ConfigDict(extra="forbid")

    ip: Annotated[
        str,
        Field(description="IP address of the network. May contain netmask, e.g. `192.168.0.0/24`."),
    ]
    mask: Optional[str] = Field(
        default=None,
        description="Optional netmask (only if not provided within the `ip` argument).",
    )
    gateway: Optional[str] = Field(
        default=None, description="Optional gateway address for the network."
    )

    add_requestor: bool = Field(
        default=True, description="If True, adds requestor with ip `requestor_ip` to the network."
    )
    requestor_ip: Optional[str] = Field(
        default=None,
        description="Ip of the requestor node in the network. Ignored if not `add_requestor`. If `None`, next free ip will be assigned.",
    )


class NodeNetworkConfig(BaseModel):
    ip: Optional[str] = Field(
        default=None,
        description="Ip of the node in the network. If `None`, next free ip will be assigned.",
    )


class MarketConfig(BaseModel):
    """Definition of the way how prepare the demand and how to process found Proposals."""

    model_config = ConfigDict(extra="forbid")

    demand: MarketConfigDemand = Field(default_factory=MarketConfigDemand)
    filters: List[ImportableFilter] = Field(
        default_factory=list,
        description="List of importable filters to be applied on each found proposal.",
    )
    sorters: List[ImportableSorter] = Field(
        default_factory=list,
        description="List of importable sorters to be applied on all found proposals.",
    )


class NodeConfig(BaseModel):
    """Definition of the details related to node creation."""

    model_config = ConfigDict(extra="forbid")

    market_config: MarketConfig = Field(default_factory=MarketConfig)
    sidecars: List[ImportableSidecar] = Field(
        default_factory=list,
        description="List of importable Sidecars that will be started with the node.",
    )
    on_start_commands: List[ImportableWorkFunc] = Field(
        default_factory=list,
        description="List of importable work functions to run when activity is about to be started.",
    )
    on_stop_commands: List[ImportableWorkFunc] = Field(
        default_factory=list,
        description="List of importable work functions to run when activity is about to be stopped.",
    )

    def combine(self, other: "NodeConfig") -> "NodeConfig":
        result = deepcopy(self.dict())

        dpath.merge(result, other.dict())

        return NodeConfig(**result)


class PaymentConfig(BaseModel):
    """Definition of the details related to payment methods."""

    model_config = ConfigDict(extra="forbid")

    address: Optional[str] = None
    network: str = "holesky"
    driver: str = "erc20"


class NodeOut(BaseModel):
    """Data related to Node."""

    model_config = ConfigDict(extra="ignore")

    node_id: str
    state: NodeState

    @classmethod
    def from_node(cls, node: "Node") -> "NodeOut":
        return cls(
            node_id=node.node_id,
            state=node.state,
        )


class ClusterOut(BaseModel):
    """Data related to Cluster."""

    model_config = ConfigDict(extra="ignore")

    cluster_id: str
    state: ClusterState
    nodes: Mapping[str, NodeOut]

    @classmethod
    def from_cluster(cls, cluster: "Cluster") -> "ClusterOut":
        return cls(
            cluster_id=cluster.cluster_id,
            state=cluster.state,
            nodes={node_id: NodeOut.from_node(node) for node_id, node in cluster.nodes.items()},
        )


class ProposalOut(BaseModel):
    """Data related to Proposal."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    proposal_id: Optional[ProposalId]
    issuer_id: Optional[str]
    state: ProposalState
    timestamp: datetime
    properties: Annotated[
        Properties,
        WithJsonSchema(
            {
                "type": "object",
            },
            mode="serialization",
        ),
    ]
