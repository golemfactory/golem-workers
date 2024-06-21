import asyncio
import importlib
import logging
from asyncio.subprocess import Process
from datetime import timedelta
from pathlib import Path
from shlex import quote
from typing import List, TypeVar, Optional
from yarl import URL

from golem.resources import Demand, Proposal, ProposalData, Network
from golem_cluster_api.exceptions import ClusterApiError

logger = logging.getLogger(__name__)

TImportType = TypeVar("TImportType")


async def collect_initial_proposals(demand: Demand, timeout: timedelta) -> List[ProposalData]:
    demand.start_collecting_events()

    proposals = []

    proposals_coro = _collect_initial_proposals(demand, proposals)

    try:
        await asyncio.wait_for(proposals_coro, timeout=timeout.total_seconds())
    except asyncio.TimeoutError:
        pass

    # demand.stop_collecting_events()

    return [await o.get_proposal_data() for o in proposals]


async def _collect_initial_proposals(demand: Demand, proposals: List[Proposal]) -> None:
    async for proposal in demand.initial_proposals():
        proposals.append(proposal)


def import_from_dotted_path(dotted_path: str):
    module_path, func_name = dotted_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), func_name)


async def run_subprocess(
    *args,
    stderr=asyncio.subprocess.DEVNULL,
    stdout=asyncio.subprocess.DEVNULL,
    detach=False,
) -> Process:
    process = await asyncio.create_subprocess_exec(
        *args,
        stderr=stderr,
        stdout=stdout,
        start_new_session=detach,
    )

    return process


async def run_subprocess_output(*args, timeout: Optional[timedelta] = None) -> bytes:
    process = await run_subprocess(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout.total_seconds() if timeout else None,
        )
    except asyncio.TimeoutError as e:
        if process.returncode is None:
            process.kill()
            await process.wait()

        raise ClusterApiError(f"Process could not finish in timeout of {timeout}!") from e

    if process.returncode != 0:
        raise ClusterApiError(
            f"Process exited with code `{process.returncode}`!\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    return stdout


def get_connection_uri(network: Network, ip: str) -> URL:
    network_url = URL(network.node._api_config.net_url)
    return network_url.with_scheme("ws") / "net" / network.id / "tcp" / ip


def get_ssh_proxy_command(connection_uri: URL, appkey: str, websocat_path: str = "websocat") -> str:
    # Using single quotes for the authentication token as double quotes are causing problems with CLI character escaping in ray
    return f"{websocat_path} asyncstdio: {connection_uri}/22 --binary -H=Authorization:'Bearer {appkey}'"


def get_ssh_command_args(
    ip: str, ssh_proxy_command: str, ssh_user: str, ssh_private_key_path: Path
) -> List[str]:
    return [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "ServerAliveInterval=300",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        f"ProxyCommand={ssh_proxy_command}",
        "-i",
        str(ssh_private_key_path),
        f"{ssh_user}@{ip}",
    ]


def get_ssh_command(
    ip: str, ssh_proxy_command: str, ssh_user: str, ssh_private_key_path: Path
) -> str:
    return " ".join(
        quote(part)
        for part in get_ssh_command_args(ip, ssh_proxy_command, ssh_user, ssh_private_key_path)
    )


async def create_ssh_key(ssh_key_path: Path) -> None:
    logger.info(f"Creating ssh key `{ssh_key_path}`...")

    ssh_key_path.parent.mkdir(parents=True, exist_ok=True)

    # FIXME: Use cryptography module instead of subprocess
    await run_subprocess_output(
        "ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", str(ssh_key_path)
    )

    logger.info(f"Creating ssh key `{ssh_key_path}` done")
