import asyncio
from collections.abc import Awaitable
from typing import List, MutableMapping, Callable

from golem.node import GolemNode
from pydantic.v1 import BaseModel

from golem_workers.cluster import Cluster


class ListClusterResponse(BaseModel):
    clusters: List[str]


def ListClusterCommand(
    golem_node: GolemNode, clusters_lock: asyncio.Lock, clusters: MutableMapping[str, Cluster]
) -> Callable[[], Awaitable[List[str]]]:
    async def do_list() -> List[str]:
        async with clusters_lock:
            return list(clusters.keys())

    return do_list
