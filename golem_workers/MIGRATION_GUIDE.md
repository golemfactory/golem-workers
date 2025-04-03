# Dependency Injection Refactoring - Migration Guide

This guide outlines the steps to migrate from the current command-based architecture to the new service-based architecture with improved dependency injection.

## 1. Overview of Changes

The refactoring introduces these major changes:

- Service interfaces in `golem_workers/services/interfaces.py`
- Service implementations in `golem_workers/services/`
- Updated container structure that separates services from resources
- FastAPI dependency injection for cleaner endpoint code
- Shift from command-centric design to service-centric design

## 2. Migration Steps

### Step 1: Switch to New Container

Update any imports from:
```python
from golem_workers.containers import Container
```

To:
```python
from golem_workers.containers_new import Container
```

### Step 2: Update Web Application Entrypoints

Change imports in your application entry points:

```python
from golem_workers.entrypoints.web.main_new import app
```

Or if creating a custom application:

```python
from golem_workers.entrypoints.web.application_new import create_application
```

### Step 3: Use Service Interfaces for Dependency Injection

When creating custom endpoints, use FastAPI dependency injection:

```python
from fastapi import Depends
from golem_workers.entrypoints.web.dependencies import get_cluster_service
from golem_workers.services.interfaces import IClusterService

@router.get("/my-endpoint")
async def my_endpoint(
    cluster_service: IClusterService = Depends(get_cluster_service)
):
    clusters = await cluster_service.list_clusters()
    return {"clusters": clusters}
```

### Step 4: Extend Services for Custom Business Logic

To add custom business logic, extend the service interfaces:

```python
from golem_workers.services.interfaces import IClusterService

class CustomClusterService(IClusterService):
    # Implement methods from IClusterService...
    
    async def custom_business_logic(self):
        # Your custom implementation
        pass
```

And register in your container:

```python
from dependency_injector import providers

container = Container()
container.services.cluster_service.override(
    providers.Factory(CustomClusterService, ...)
)
```

## 3. Benefits of the New Architecture

- **Improved testability**: Service interfaces can be easily mocked
- **Cleaner endpoint code**: FastAPI dependency injection simplifies endpoints
- **Better separation of concerns**: Business logic in services, not commands
- **Maintainability**: Clear boundaries between components
- **Extensibility**: Easy to add new services or override existing ones

## 4. Examples

### Old Pattern (Command-based):

```python
@router.get("/cluster")
async def list_clusters(request: Request) -> List[str]:
    command = await request.app.state.container.list_cluster_command()
    return await command()
```

### New Pattern (Service-based):

```python
@router.get("/cluster")
async def list_clusters(
    cluster_service: IClusterService = Depends(get_cluster_service)
) -> List[str]:
    return await cluster_service.list_clusters()
```

## 5. Transitioning Gradually

You can adopt the new pattern gradually:

1. Start by adding the service interfaces
2. Implement service classes that wrap existing commands
3. Update the container to use both old commands and new services
4. Gradually update endpoints to use the new services
5. Eventually replace the command-based implementations

## 6. Testing

Use the service interfaces for easier testing:

```python
from unittest.mock import AsyncMock
import pytest
from golem_workers.services.interfaces import IClusterService

@pytest.fixture
def mock_cluster_service():
    service = AsyncMock(spec=IClusterService)
    service.list_clusters.return_value = ["cluster1", "cluster2"]
    return service

async def test_list_clusters(mock_cluster_service):
    result = await mock_cluster_service.list_clusters()
    assert result == ["cluster1", "cluster2"]
```