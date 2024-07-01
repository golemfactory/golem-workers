from abc import ABC

import collections

from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Union, Sequence, Tuple

import dpath
from typing_extensions import Annotated

from golem.payload import PayloadSyntaxParser, Properties
from golem.payload import defaults as payload_defaults
from golem.resources import Allocation, DemandBuilder, ProposalId
from golem.resources.proposal.data import ProposalState
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, RootModel

from golem_cluster_api.utils import import_from_dotted_path

if TYPE_CHECKING:
    from golem_cluster_api.cluster.cluster import Cluster
    from golem_cluster_api.cluster.node import Node


class RequestBaseModel(BaseModel, ABC):
    model_config = ConfigDict(extra="forbid")


class ResponseBaseModel(BaseModel, ABC):
    model_config = ConfigDict(extra="ignore")


class State(Enum):
    """Enum related to cluster or node state."""

    CREATED = "created"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    REMOVING = "removing"


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

    def import_object(self) -> Tuple[Any, Sequence, Mapping]:
        if isinstance(self.root, str):
            path = self.root
            data = []  # empty positional args
        else:
            path = next(iter(self.root))
            data = self.root[path]

        imported_object = import_from_dotted_path(path)

        if isinstance(data, collections.Sequence):
            args = data
            kwargs = {}
        else:
            args = []
            kwargs = data

        return imported_object, args, kwargs


ImportablePayload = ImportableElement
ImportableFilter = ImportableElement
ImportableSidecar = ImportableElement
ImportableWorkFunc = ImportableElement


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

    async def create_demand_builder(self, allocation: Allocation) -> DemandBuilder:
        demand_builder = DemandBuilder()

        all_payloads = [
            payload_defaults.ActivityInfo(
                lifetime=payload_defaults.DEFAULT_LIFETIME, multi_activity=True
            ),
            payload_defaults.PaymentInfo(),
            await allocation.get_demand_spec(),
        ]

        for payload in self.payloads:
            payload_class, payload_args, payload_kwargs = payload.import_object()

            all_payloads.append(payload_class(*payload_args, **payload_kwargs))

        for demand_spec in all_payloads:
            await demand_builder.add(demand_spec)

        # TODO MVP: move Properties creation to object parsing?
        demand_builder.add_properties(Properties(self.properties))

        if self.constraints:
            # TODO MVP: move Constraints creation to object parsing?
            constraints = PayloadSyntaxParser.get_instance().parse_constraints(
                "(& {})".format(
                    " ".join(c if c.startswith("(") else f"({c})" for c in self.constraints)
                )
            )
            demand_builder.add_constraints(constraints)

        return demand_builder


class MarketConfig(BaseModel):
    """Definition of the way of how prepare the demand and how to process found proposals."""

    model_config = ConfigDict(extra="forbid")

    demand: MarketConfigDemand = Field(default_factory=MarketConfigDemand)
    filters: List[ImportableFilter] = Field(
        default_factory=list,
        description="List of importable filters to be applied on each found proposal.",
    )
    sorters: List[ImportableElement] = Field(
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
    model_config = ConfigDict(extra="forbid")

    address: Optional[str] = None
    network: str = "holesky"
    driver: str = "erc20"


class NodeOut(BaseModel):
    """Data related to node."""

    model_config = ConfigDict(extra="ignore")

    node_id: str
    state: State

    @classmethod
    def from_node(cls, node: "Node") -> "NodeOut":
        return cls(
            node_id=node.node_id,
            state=node.state,
        )


class ClusterOut(BaseModel):
    """Data related to cluster."""

    model_config = ConfigDict(extra="ignore")

    cluster_id: str
    state: State
    nodes: Mapping[str, NodeOut]

    @classmethod
    def from_cluster(cls, cluster: "Cluster") -> "ClusterOut":
        return cls(
            cluster_id=cluster.cluster_id,
            state=cluster.state,
            nodes={node_id: NodeOut.from_node(node) for node_id, node in cluster.nodes.items()},
        )


class ProposalOut(BaseModel):
    """Data related to proposal."""

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
