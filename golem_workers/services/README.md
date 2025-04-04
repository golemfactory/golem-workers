# Services Architecture

This folder contains the service interfaces and implementations used throughout the application.

## Overview

The services architecture follows these principles:

1. **Interface-first design**: All services implement a common interface
2. **Dependency injection**: Services receive dependencies through constructors
3. **Single responsibility**: Each service focuses on a specific domain area
4. **Testability**: Services can be mocked and tested in isolation

## Structure

- `interfaces.py` - Contains all service interfaces
- `proposals.py` - Service for managing proposals
- `clusters.py` - Service for managing clusters
- `nodes.py` - Service for managing nodes within clusters
- `port_allocation_service.py` - Service for port allocation

## Usage

### Dependency Injection with FastAPI

```python
from fastapi import Depends
from golem_workers.entrypoints.web.dependencies import get_cluster_service
from golem_workers.services.interfaces import IClusterService

@router.get("/clusters")
async def list_clusters(
    cluster_service: IClusterService = Depends(get_cluster_service)
):
    return await cluster_service.list_clusters()
```

### Using Services in Other Services

```python
class CombinedService:
    def __init__(
        self,
        cluster_service: IClusterService,
        node_service: INodeService,
    ):
        self._cluster_service = cluster_service
        self._node_service = node_service
        
    async def get_cluster_with_nodes(self, cluster_id: str):
        cluster = await self._cluster_service.get_cluster(cluster_id)
        # Additional business logic
        return cluster
```

## Extending Services

To extend a service with custom behavior:

1. Create a new class that implements the appropriate interface
2. Override the container factory in your application setup:

```python
from dependency_injector import providers
from golem_workers.containers import Container
from my_app.services import CustomClusterService

container = Container()
container.services.cluster_service.override(
    providers.Factory(CustomClusterService, ...)
)
```
