from typing import List

from golem.payload import Payload
from pydantic import BaseModel
from ray_on_golem.server.models import NodeConfigData


class PayloadConfig(BaseModel):
    payload: Payload


class ClusterConfig(BaseModel):
    id_: str
    node_config: NodeConfigData


class CreateNodePayload(BaseModel):
    proposal_ids: List[str]
