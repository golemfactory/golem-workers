from typing import Union, Sequence, Optional

import asyncio

import logging
from datetime import timedelta
from pathlib import Path

from golem.resources import BatchError
from golem_cluster_api.context import WorkContext
from golem_cluster_api.utils import (
    create_ssh_key,
    get_ssh_command,
    get_ssh_proxy_command,
    get_connection_uri,
)

logger = logging.getLogger(__name__)


async def deploy_and_start_with_vpn(
    context: WorkContext, deploy_timeout_minutes: Optional[float] = 5
) -> None:
    deploy_action = context.deploy(
        {"net": [context.extra["network"].deploy_args(context.extra["ip"])]}
    )

    if deploy_timeout_minutes:
        deploy_timeout_minutes = timedelta(minutes=deploy_timeout_minutes).total_seconds()

    await asyncio.wait_for(deploy_action, timeout=deploy_timeout_minutes)

    await context.start()


async def prepare_and_run_ssh_server(context: WorkContext, ssh_key_path: str) -> None:
    logger.info("Preparing `%s` activity ssh keys...", context.activity)

    ssh_private_key_path = Path(ssh_key_path)
    if not ssh_private_key_path.exists():
        await create_ssh_key(ssh_private_key_path)

    with ssh_private_key_path.with_suffix(".pub").open("r") as f:
        ssh_public_key_data = str(f.read())

    await context.gather(
        context.run("mkdir -p /root/.ssh"),
        context.run(f'echo "{ssh_public_key_data}" >> /root/.ssh/authorized_keys'),
    )

    logger.info("Preparing `%s` activity ssh keys done", context.activity)

    logger.info("Starting `%s` activity ssh server...", context.activity)

    await context.run("apt install openssh-server")
    await context.run("service ssh start")

    logger.info("Starting `%s` activity ssh server done", context.activity)

    print(
        get_ssh_command(
            context.extra["ip"],
            get_ssh_proxy_command(
                get_connection_uri(context.extra["network"], context.extra["ip"]),
                context.extra["network"].node.app_key,
            ),
            "root",
            ssh_private_key_path,
        )
    )


async def run_in_shell(context: WorkContext, *commands: Union[str, Sequence[str]]) -> None:
    commands = [context.run(command, shell=True) for command in commands]

    try:
        await context.gather(*commands)
    except BatchError as e:
        print(list(event.stderr for event in e.batch.events))
        print(list(event.stdout for event in e.batch.events))

        raise


async def stop_activity(context: WorkContext) -> None:
    await context.destroy()
