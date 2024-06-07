from pathlib import Path
from typing import List, Optional

from golem.payload import Payload
from pydantic import BaseModel, Field
from ray_on_golem.server.models import NodeConfigData


class NodeConfig(BaseModel):
    node_config_data: Optional[NodeConfigData] = None
    custom_payloads: List[Payload] = Field(default_factory=list)


class CreateClusterBody(BaseModel):
    cluster_id: str
    node_config: NodeConfig


class CreateNodesBody(BaseModel):
    cluster_id: str
    proposal_ids: List[str]
    proposal_pool_id: Optional[str]
    node_type: str = "default"  # TODO
    node_config: NodeConfig = Field(default_factory=NodeConfig)
    node_count: int = 1


class CreateProposalPoolBody(BaseModel):
    ...


class DeleteClusterBody(BaseModel):
    cluster_id: str


class DeleteNodeBody(BaseModel):
    cluster_id: str
    node_id: str


class DeleteProposalPoolBody(BaseModel):
    ...


class ExecuteCommandsBody(BaseModel):
    ...


class GetClusterBody(BaseModel):
    cluster_id: str


class GetNodeBody(BaseModel):
    cluster_id: str
    node_id: str


class GetCommandsBody(BaseModel):
    ...


class GetProposalsBody(BaseModel):
    node_config: NodeConfig = Field(default_factory=NodeConfig)


class ClusterParametersData(BaseModel):
    webserver_port: int
    ray_gcs_expose_port: Optional[int]
    enable_registry_stats: bool
    payment_network: str
    payment_driver: str
    total_budget: float
    node_config: NodeConfigData
    ssh_private_key: Path
    ssh_user: str
    webserver_datadir: Optional[str] = None

    class Config:
        extra = "forbid"
