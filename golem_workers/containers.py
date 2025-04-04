import asyncio
from contextlib import AsyncExitStack
from typing import Sequence

from dependency_injector import providers
from dependency_injector.containers import DeclarativeContainer

from golem.node import GolemNode
from golem_workers.golem import DriverListAllocationPaymentManager
from golem_workers.models import ImportableContext
from golem_workers.services import (
    ProposalService,
    ClusterService,
    NodeService,
    PortAllocationService,
)
from golem_workers.services.port_allocation import AllocationManager


async def golem_node_context(app_key: str):
    golem_node = GolemNode(app_key=app_key)

    async with golem_node:
        yield golem_node


async def get_port_allocation_manager():
    port_allocation_manager = AllocationManager()

    try:
        yield port_allocation_manager
    finally:
        port_allocation_manager.shutdown()


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


class ServicesContainer(DeclarativeContainer):
    """Container for service providers."""

    # Dependencies from parent container
    config = providers.Configuration()
    golem_node = providers.Dependency()
    clusters = providers.Dependency()
    clusters_lock = providers.Dependency()
    port_allocation_manager = providers.Dependency()

    port_allocation_service = providers.Factory(
        PortAllocationService,
        allocation_manager=port_allocation_manager,
    )

    # Service providers
    proposal_service = providers.Factory(
        ProposalService,
        golem_node=golem_node,
        payment_manager_factory=DriverListAllocationPaymentManager,
    )

    cluster_service = providers.Factory(
        ClusterService,
        golem_node=golem_node,
        clusters_lock=clusters_lock,
        clusters=clusters,
        port_allocation_service=port_allocation_service,
    )

    node_service = providers.Factory(
        NodeService,
        golem_node=golem_node,
        clusters=clusters,
        port_allocation_service=port_allocation_service,
    )


class Container(DeclarativeContainer):
    """Main application container."""

    # Configuration
    settings = providers.Configuration()

    # Resources
    global_contexts = providers.Resource(
        global_contexts_context,
        settings.global_contexts,
    )

    golem_node = providers.Resource(
        golem_node_context,
        app_key=settings.yagna_appkey,
    )

    clusters = providers.Resource(clusters_context)
    clusters_lock = providers.Singleton(asyncio.Lock)

    port_allocation_manager = providers.Resource(
        get_port_allocation_manager,
    )

    # Services container with injected dependencies
    services = providers.Container(
        ServicesContainer,
        config=settings,
        golem_node=golem_node,
        clusters=clusters,
        clusters_lock=clusters_lock,
        port_allocation_manager=port_allocation_manager,
    )
