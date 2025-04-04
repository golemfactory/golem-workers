from typing import Union, Sequence, Optional

import asyncio

import logging
from datetime import timedelta
from pathlib import Path

from golem.resources import BatchError, DeployArgsType, Network

from golem_workers.context import WorkContext
from golem_workers.utils import (
    create_ssh_key,
    get_ssh_command,
    get_ssh_proxy_command,
    get_connection_uri,
)

logger = logging.getLogger(__name__)


async def deploy_and_start_activity(
    context: WorkContext, /, deploy_timeout_minutes: Optional[float] = 5
) -> None:
    """Deploy and start activity.

    Depending on image size and state of the image cache on the provider side, deploy step can take considerable amount of time.

    Args:
        context: Externally provided WorkContext object bound to the activity.
        deploy_timeout_minutes: Amount of minutes after exception will be raised if deploy will be not completed.
    """

    if deploy_timeout_minutes:
        deploy_timeout_minutes = timedelta(minutes=deploy_timeout_minutes).total_seconds()

    await asyncio.wait_for(context.deploy(), timeout=deploy_timeout_minutes)

    await context.start()


async def prepare_and_run_ssh_server(context: WorkContext, /, ssh_private_key_path: str) -> None:
    """Prepare and run SSH server on the provider.

    Note:
        This work function requires `ssh-keygen` binary to be available on the requestor if given ssh key is not existing.

    Note:
        This work function requires activity to be previously deployed and started.

    Note:
        This work function is compatible with VM-like runtimes and depends on `apt` and `service` binaries to be available on the provider.

    Args:
        context: Externally provided WorkContext object bound to the activity.
        ssh_private_key_path:
            Path for SSH private key.
            If provided it must have correlating public key file with the `.pub` suffix at the same path.
            If given path is not existing, ssh keys will be generated under given destination.
    """

    if not len(context.default_deploy_args.get("net", [])):
        raise RuntimeError("Activity needs to be connected to any VPN network!")

    logger.info("Preparing `%s` activity ssh keys...", context.activity)

    ssh_private_key_path = Path(ssh_private_key_path)
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

    network_args: DeployArgsType = context.default_deploy_args["net"][0]

    print(
        get_ssh_command(
            network_args["nodeIp"],
            get_ssh_proxy_command(
                get_connection_uri(
                    Network(context.golem_node, network_args["id"]), network_args["nodeIp"]
                ),
                context.golem_node.app_key,
            ),
            "root",
            ssh_private_key_path,
        )
    )


async def run_in_shell(context: WorkContext, /, *commands: Union[str, Sequence[str]]) -> None:
    """Run shell commands.

    Note:
        This work function requires activity to be previously deployed and started.

    Args:
        context: Externally provided WorkContext object bound to the activity.
        *commands: Sequence of commands to run as a shell commands in a single string or list of raw exec arguments.
    """

    commands = [context.run(command, shell=True) for command in commands]

    try:
        await context.gather(*commands)
    except BatchError as e:
        print(list(event.stderr for event in e.batch.events))
        print(list(event.stdout for event in e.batch.events))

        raise


async def wait_for_http_endpoint(
    context: WorkContext,
    *,
    network_name: str,
    port: int,
    path: str = "/",
    timeout_minutes: float = 15,
) -> None:
    import websockets

    key = context.golem_node.app_key
    logger.info("Waiting for http endpoint %s:%s%s", network_name, port, path)
    node = context.extra["node"]

    network, node_ip = node.get_network(network_name)
    uri = get_connection_uri(network, node_ip)

    async def try_connect():
        try:
            async with websockets.connect(
                f"{uri}/{port}",
                additional_headers={
                    "Authorization": f"Bearer {key}",
                },
            ) as websocket:
                await websocket.send(f"GET {path} HTTP/1.1\r\nHost: {node_ip}:{port}\r\n\r\n")
                data = await websocket.recv(False)
                return data[0:12] == b"HTTP/1.1 200"
        except websockets.exceptions.WebSocketException:
            return False

    async def wait_for_endpoint():
        while not await try_connect():
            await asyncio.sleep(5)

    timeout_seconds = timedelta(minutes=timeout_minutes).total_seconds()
    await asyncio.wait_for(wait_for_endpoint(), timeout=timeout_seconds)
    logger.info("Http endpoint %s:%s%s is ready", network_name, port, path)


async def stop_activity(context: WorkContext, /) -> None:
    """Stop and destroy activity.

    Args:
        context: Externally provided WorkContext object bound to the activity.
    """

    await context.destroy()
