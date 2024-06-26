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


class RequestBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class State(Enum):
    CREATED = "created"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    REMOVING = "removing"


class ImportableElement(RootModel):
    root: Union[
        str,
        Annotated[Mapping[str, Union[Mapping, Sequence]], Field(min_length=1, max_length=1)]
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
ImportableCommand = ImportableElement

class MarketConfigDemand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payloads: List[ImportablePayload] = Field(default_factory=list)
    properties: Mapping[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)

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
    model_config = ConfigDict(extra="forbid")

    demand: MarketConfigDemand = Field(default_factory=MarketConfigDemand)
    filters: List[ImportableFilter] = Field(default_factory=list)


class ExposePortEntryDirection(Enum):
    REQUESTOR_TO_PROVIDER = "requestor-to-provider"
    PROVIDER_TO_REQUESTOR = "provider-to-requestor"


class ExposePortEntry(
    BaseModel
):  # TODO: To be used when yagna would have built-in two-directional proxy funcionality
    model_config = ConfigDict(extra="forbid")

    requestor_port: int
    provider_port: int
    direction: ExposePortEntryDirection


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_config: MarketConfig = Field(default_factory=MarketConfig)
    sidecars: List[ImportableSidecar] = Field(default_factory=list)
    on_start_commands: List[ImportableCommand] = Field(default_factory=list)
    on_stop_commands: List[ImportableCommand] = Field(default_factory=list)

    def combine(self, other: "NodeConfig") -> "NodeConfig":
        result = deepcopy(self.dict())

        dpath.merge(result, other.dict())

        return NodeConfig(**result)


class PaymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: Optional[str] = None
    network: str = "holesky"
    driver: str = "erc20"
    total_budget: float = 5


class NodeOut(BaseModel):
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


class GetProposalsRequest(RequestBaseModel):
    market_config: MarketConfig
    collection_time_seconds: float = 5


class GetProposalsResponse(ResponseBaseModel):
    proposals: List[ProposalOut]


class CreateClusterRequest(RequestBaseModel):
    cluster_id: str
    payment_config: Optional[PaymentConfig] = Field(default_factory=PaymentConfig)
    node_types: Mapping[str, NodeConfig] = Field(default_factory=dict)


class CreateClusterResponse(ResponseBaseModel):
    cluster: ClusterOut


class GetClusterRequest(RequestBaseModel):
    cluster_id: str


class GetClusterResponse(ResponseBaseModel):
    cluster: ClusterOut


class DeleteClusterRequest(RequestBaseModel):
    cluster_id: str


class DeleteClusterResponse(ResponseBaseModel):
    cluster: ClusterOut


class CreateNodeRequest(RequestBaseModel):
    cluster_id: str
    proposal_id: str
    node_type: str = "default"  # TODO
    node_config: NodeConfig = Field(default_factory=NodeConfig)


class CreateNodeResponse(ResponseBaseModel):
    node: NodeOut


class GetNodeRequest(BaseModel):
    cluster_id: str
    node_id: str


class GetNodeResponse(ResponseBaseModel):
    node: NodeOut


class DeleteNodeRequest(BaseModel):
    cluster_id: str
    node_id: str


class DeleteNodeResponse(ResponseBaseModel):
    node: NodeOut
