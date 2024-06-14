from datetime import timedelta
from typing import Any, Dict

from golem.managers import WorkContext


class ClusterAPIWorkContext(WorkContext):
    # TODO MVP: move extras to `WorkContext`

    def __init__(self, extras: Dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.network = extras.get("network")
        self.ip = extras.get("ip")


async def deploy(context: ClusterAPIWorkContext) -> None:
    deploy_args = {"net": [context.network.deploy_args(context.ip)]}
    await context.deploy(deploy_args, timeout=timedelta(minutes=5))


async def start(context: WorkContext) -> None:
    await context.start()
