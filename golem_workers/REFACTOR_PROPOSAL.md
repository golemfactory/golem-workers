# Dependency Injection Refactor Proposal

## Current Implementation

The current dependency injection implementation:
- Uses `dependency-injector` library with a monolithic `Container` class
- Has direct `await request.app.state.container.[command]()` calls in endpoints
- Manages multiple resource lifecycles in separate resource providers
- Lacks clear separation between service interfaces and implementations

## Proposed Changes

### 1. Use Interface Abstractions

Create interface abstractions for all services to improve testability and maintainability:

```python
# golem_workers/services/interfaces.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from golem_workers.models import ProposalOut

class IProposalService(ABC):
    @abstractmethod
    async def get_proposals(self, request_data) -> List[ProposalOut]:
        pass
        
class IClusterService(ABC):
    @abstractmethod
    async def create_cluster(self, request_data): pass
    
    @abstractmethod
    async def list_clusters(self) -> List[str]: pass
    
    @abstractmethod
    async def get_cluster(self, cluster_id: str): pass
    
    @abstractmethod
    async def delete_cluster(self, cluster_id: str): pass
```

### 2. Implement Service Classes

Create service classes that implement these interfaces:

```python
# golem_workers/services/proposals.py
from golem_workers.services.interfaces import IProposalService

class ProposalService(IProposalService):
    def __init__(self, golem_node, payment_manager):
        self.golem_node = golem_node
        self.payment_manager = payment_manager
        
    async def get_proposals(self, request_data):
        # Implementation here
        pass
```

### 3. Refactor Container with Service Modules

Split the container into modules for better organization:

```python
# golem_workers/containers.py
from dependency_injector import containers, providers
from golem_workers.services.proposals import ProposalService
from golem_workers.services.clusters import ClusterService

class ServicesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    golem_node = providers.Dependency()
    
    proposal_service = providers.Factory(
        ProposalService,
        golem_node=golem_node,
        payment_manager=providers.Factory(DriverListAllocationPaymentManager),
    )
    
    cluster_service = providers.Factory(
        ClusterService,
        golem_node=golem_node,
        clusters=providers.Dependency(),
        clusters_lock=providers.Dependency(),
    )

class Container(containers.DeclarativeContainer):
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
    
    # Services container with injected dependencies
    services = providers.Container(
        ServicesContainer,
        config=settings,
        golem_node=golem_node,
        clusters=clusters,
        clusters_lock=clusters_lock,
    )
```

### 4. Simplify Endpoint Access with FastAPI Dependency Injection

Leverage FastAPI's dependency injection:

```python
# golem_workers/entrypoints/web/dependencies.py
from fastapi import Depends, Request
from golem_workers.services.interfaces import IProposalService, IClusterService

async def get_proposal_service(request: Request) -> IProposalService:
    return await request.app.state.container.services.proposal_service()

async def get_cluster_service(request: Request) -> IClusterService:
    return await request.app.state.container.services.cluster_service()
```

### 5. Refactor Endpoints to Use Service Dependencies

```python
# golem_workers/entrypoints/web/endpoints.py
from golem_workers.entrypoints.web.dependencies import get_proposal_service, get_cluster_service

@router.post("/get-proposals", tags=[Tags.MISC], responses=responses)
async def get_proposals(
    request_data: commands.GetProposalsRequest,
    proposal_service: IProposalService = Depends(get_proposal_service),
) -> commands.GetProposalsResponse:
    return await proposal_service.get_proposals(request_data)

@router.get("/cluster", tags=[Tags.CLUSTERS])
async def list_clusters(
    cluster_service: IClusterService = Depends(get_cluster_service),
) -> List[str]:
    return await cluster_service.list_clusters()
```

## Benefits

1. **Improved Testability**: Service interfaces can be mocked easily
2. **Better Separation of Concerns**: Commands become thin wrappers around services
3. **Reduced Duplication**: Common logic stays in services, not commands
4. **Simpler Endpoint Code**: FastAPI handles dependency resolution
5. **Modularity**: Container is split into logical modules
6. **Clarity**: Clear distinction between interfaces and implementations

## Implementation Steps

1. Create service interfaces
2. Implement service classes
3. Refactor container structure
4. Add FastAPI dependency injection
5. Refactor endpoints to use services directly
6. Update tests to use mocked services