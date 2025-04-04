from pydantic import Field, model_validator, BaseModel, ConfigDict
from typing import Mapping, Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

from golem_workers.models import (
    PaymentConfig,
    NodeConfig,
    BudgetConfig,
    NetworkConfig,
    AllocationConfig,
    NodeNetworkConfig,
    ClusterOut,
    NodeOut,
    ProposalOut,
)


class CreateClusterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: str = "default"

    labels: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata labels for the cluster in key-value format.",
    )

    payment_config: PaymentConfig = Field(
        default_factory=PaymentConfig,
        description="Payment configuration that will be applied on the whole cluster. Can be replaced by `payment_config` in `budget_types`.",
    )
    allocation_config: Optional[AllocationConfig] = Field(
        default=None,
        description="Allocation configuration that will be applied on the whole cluster. Can be replaced by `allocation_config` in `budget_types`.",
    )
    budget_types: Mapping[str, BudgetConfig] = Field(
        min_length=1,
        description="Collection of Budget configurations that nodes can reference by the key.",
    )
    network_types: Mapping[str, NetworkConfig] = Field(
        default_factory=dict,
        description="Collection of Network configurations that nodes can reference by the key.",
    )
    node_types: Mapping[str, NodeConfig] = Field(
        default_factory=dict,
        description="Collection of Node configurations that nodes can reference by the key. Can be extended by the node.",
    )


class CreateNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: str = "default"
    budget_type: str = "default"
    node_networks: Mapping[str, NodeNetworkConfig] = Field(
        default_factory=dict,
        description="",
    )
    node_type: Optional[str] = "default"
    node_config: Optional[NodeConfig] = None
    labels: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_node_type_and_node_config(self):
        if self.node_type is None and self.node_config is None:
            raise ValueError("At least one of `node_type` or `node_config` must be defined!")

        return self


# Request models for proposals
class GetProposalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    market_config: Optional[Dict[str, Any]] = Field(default_factory=dict)


# Response models
class GetProposalsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    proposals: List[ProposalOut]


class CreateClusterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cluster: ClusterOut


class GetClusterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cluster: ClusterOut


class DeleteClusterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cluster: ClusterOut


class CreateNodeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node: NodeOut


class GetNodeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node: NodeOut


class DeleteNodeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node: NodeOut


# Port Allocation types
class AllocationStatus(str, Enum):
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    RELEASED = "released"


class PortAllocationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_port: int
    max_port: int
    expiration_minutes: int


class PortAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocation_id: str
    port: int
    status: AllocationStatus
    expires_at: datetime
    cluster_id: Optional[str] = None
    node_id: Optional[str] = None


class PortAllocationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocation_id: str
    port: int
    status: AllocationStatus
    expires_at: str
    cluster_id: Optional[str] = None
    node_id: Optional[str] = None


class PortReleaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: int
    status: AllocationStatus


class ClusterPortReleaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    released_ports: List[int]
    count: int


class PortStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    total_ports: int
    allocated_ports: int
    in_use_ports: int
    available_ports: int
