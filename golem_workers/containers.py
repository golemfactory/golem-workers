import asyncio
from contextlib import AsyncExitStack
from typing import Sequence

from dependency_injector import providers
from dependency_injector.containers import DeclarativeContainer

from golem.node import GolemNode
from golem_workers import commands
from golem_workers.golem import DriverListAllocationPaymentManager
from golem_workers.models import ImportableContext


async def golem_node_context(app_key: str):
    golem_node = GolemNode(app_key=app_key)

    async with golem_node:
        yield golem_node


async def clusters_context():
    clusters = {}

    yield clusters

    for cluster in clusters.values():
        await cluster.stop()


async def global_contexts_context(global_contexts: Sequence[ImportableContext]):
    contexts = []

    for context_def in global_contexts:
        context_class, context_args, context_kwargs = context_def.import_object()
        contexts.append(context_class(*context_args, **context_kwargs))

    async with AsyncExitStack() as stack:
        for context in contexts:
            await stack.enter_async_context(context)

        yield


class Container(DeclarativeContainer):
    # Use built-in way for pydantic settings loading after
    # https://github.com/ets-labs/python-dependency-injector/issues/755
    # settings = providers.Configuration(pydantic_settings=[Settings()])
    settings = providers.Configuration()

    global_contexts = providers.Resource(
        global_contexts_context,
        settings.global_contexts,
    )

    golem_node = providers.Resource(
        golem_node_context,
        app_key=settings.yagna_appkey,
    )

    clusters = providers.Resource(
        clusters_context,
    )
    clusters_lock = providers.Singleton(asyncio.Lock)

    # Commands
    get_proposal_command = providers.Factory(
        commands.GetProposalsCommand,
        golem_node,
        DriverListAllocationPaymentManager,
    )
    create_cluster_command = providers.Factory(
        commands.CreateClusterCommand,
        golem_node,
        clusters_lock,
        clusters,
    )
    get_cluster_command = providers.Factory(
        commands.GetClusterCommand,
        clusters,
    )
    delete_cluster_command = providers.Factory(
        commands.DeleteClusterCommand,
        clusters_lock,
        clusters,
    )
    create_node_command = providers.Factory(
        commands.CreateNodeCommand,
        golem_node,
        clusters,
    )
    get_node_command = providers.Factory(
        commands.GetNodeCommand,
        clusters,
    )
    delete_node_command = providers.Factory(
        commands.DeleteNodeCommand,
        clusters,
    )
