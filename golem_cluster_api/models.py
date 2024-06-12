from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Mapping, Any

from golem.payload import Payload, Properties
from golem.resources import ProposalId
from golem.resources.proposal.data import ProposalState


class RequestBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ResponseBaseModel(BaseModel):
    model_config = ConfigDict(extra='ignore')


class State(Enum):
    CREATED = 'created'
    STARTING = 'starting'
    STARTED = 'started'
    STOPPING = 'stopping'
    STOPPED = 'stopped'
    REMOVING = 'removing'


class MarketConfigDemand(BaseModel):
    model_config = ConfigDict(extra='forbid')

    payloads: Mapping[str, Any] = Field(default_factory=dict)
    properties: Mapping[str, Any] = Field(default_factory=dict)
    # constraints: List[str] = Field(default_factory=list)


class MarketConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    demand: MarketConfigDemand
    budget_control: Mapping[str, Any] = Field(default_factory=dict)


class ExposePortEntryDirection(Enum):
    REQUESTOR_TO_PROVIDER = 'requestor-to-provider'
    PROVIDER_TO_REQUESTOR = 'provider-to-requestor'


class ExposePortEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')

    requestor_port: int
    provider_port: int
    direction: ExposePortEntryDirection


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    market_config: Optional[MarketConfig] = None
    startup_commands: List[str] = Field(default_factory=list)
    expose_ports: List[ExposePortEntry] = Field(default_factory=list)
    custom_payloads: List[Payload] = Field(default_factory=list)


class PaymentConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    address: Optional[str] = None
    network: str = 'holesky'
    driver: str = 'erc20'
    total_budget: float = 5


class ProposalOut(BaseModel):
    model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True)

    proposal_id: Optional[ProposalId]
    issuer_id: Optional[str]
    state: ProposalState
    timestamp: datetime
    properties: Properties


class GetProposalsRequest(RequestBaseModel):
    market_config: MarketConfig
    collection_time_seconds: float = 5


class GetProposalsResponse(BaseModel):
    proposals: List[ProposalOut]


class CreateClusterRequest(RequestBaseModel):
    cluster_id: str
    payment_config: Optional[PaymentConfig] = Field(default_factory=PaymentConfig)
    node_types: Mapping[str, NodeConfig] = Field(default_factory=dict)


class ClusterOut(BaseModel):
    model_config = ConfigDict(extra='ignore')

    cluster_id: str


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


class CreateNodesBody(BaseModel):
    cluster_id: str
    proposal_ids: List[str]
    proposal_pool_id: Optional[str]
    node_type: str = "default"  # TODO
    node_config: NodeConfig = Field(default_factory=NodeConfig)
    node_count: int = 1


class CreateProposalPoolBody(BaseModel):
    ...


class DeleteNodeBody(BaseModel):
    cluster_id: str
    node_id: str


class DeleteProposalPoolBody(BaseModel):
    ...


class ExecuteCommandsBody(BaseModel):
    ...


class GetNodeBody(BaseModel):
    cluster_id: str
    node_id: str


class GetCommandsBody(BaseModel):
    ...
