import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from golem.node import GolemNode

from golem_workers.cluster import Cluster, Node
from golem_workers.exceptions import ObjectNotFound
from golem_workers.models import NodeConfig, BudgetScope, NodeOut, NodeState
from golem_workers.services.nodes import NodeService
from golem_workers.services.types import (
    CreateNodeRequest,
    CreateNodeResponse,
    GetNodeResponse,
    DeleteNodeResponse,
)


@pytest.fixture
def golem_node():
    return MagicMock(spec=GolemNode)


@pytest.fixture
def mock_cluster():
    cluster = MagicMock(spec=Cluster)
    cluster.create_node = AsyncMock()
    cluster.delete_node = AsyncMock()
    return cluster


@pytest.fixture
def mock_node():
    node = MagicMock(spec=Node)
    node.node_id = "test-node-id"
    return node


@pytest.fixture
def mock_node_out():
    return NodeOut(node_id="test-node-id", state=NodeState.CREATED, network_ips={}, labels={})


@pytest.fixture
def node_service(golem_node, mock_cluster):
    clusters = {"test-cluster": mock_cluster}
    return NodeService(golem_node=golem_node, clusters=clusters)


class TestNodeService:
    async def test_get_cluster_success(self, node_service, mock_cluster):
        # Test getting existing cluster
        cluster = node_service._get_cluster("test-cluster")
        assert cluster == mock_cluster

    async def test_get_cluster_not_found(self, node_service):
        # Test getting non-existing cluster
        with pytest.raises(ObjectNotFound) as excinfo:
            node_service._get_cluster("non-existing-cluster")
        assert "does not exists" in str(excinfo.value)

    async def test_get_node_success(self, node_service, mock_cluster, mock_node):
        # Setup
        mock_cluster.nodes = {"test-node-id": mock_node}

        # Test getting existing node
        node = node_service._get_node(mock_cluster, "test-node-id")
        assert node == mock_node

    async def test_get_node_not_found(self, node_service, mock_cluster):
        # Setup
        mock_cluster.nodes = {}

        # Test getting non-existing node
        with pytest.raises(ObjectNotFound) as excinfo:
            node_service._get_node(mock_cluster, "non-existing-node")
        assert "does not exists in cluster" in str(excinfo.value)

    async def test_prepare_node_config_no_node_type(self, node_service, mock_cluster):
        # Test when node_type is None
        node_config = NodeConfig()
        result = node_service._prepare_node_config(mock_cluster, None, node_config)
        assert result == node_config

    async def test_prepare_node_config_with_node_type_only(self, node_service, mock_cluster):
        # Setup
        node_type = "test-node-type"
        type_config = NodeConfig()
        mock_cluster.get_node_type_config.return_value = type_config

        # Test when only node_type is provided
        result = node_service._prepare_node_config(mock_cluster, node_type, None)
        assert result == type_config
        mock_cluster.get_node_type_config.assert_called_once_with(node_type)

    async def test_prepare_node_config_with_both(self, node_service, mock_cluster):
        # Setup
        node_type = "test-node-type"
        type_config = MagicMock()  # Use MagicMock instead of NodeConfig
        node_config = NodeConfig()
        combined_config = NodeConfig()

        mock_cluster.get_node_type_config.return_value = type_config
        type_config.combine.return_value = combined_config

        # Test when both are provided
        result = node_service._prepare_node_config(mock_cluster, node_type, node_config)
        assert result == combined_config
        mock_cluster.get_node_type_config.assert_called_once_with(node_type)
        type_config.combine.assert_called_once_with(node_config)

    async def test_prepare_node_config_type_not_found(self, node_service, mock_cluster):
        # Setup
        mock_cluster.get_node_type_config.return_value = None

        # Test when node_type doesn't exist
        with pytest.raises(ObjectNotFound) as excinfo:
            node_service._prepare_node_config(mock_cluster, "non-existing-type", None)
        assert "does not exists in the cluster" in str(excinfo.value)

    async def test_validate_budget_config_success(self, node_service, mock_cluster):
        # Setup
        budget_type = "test-budget"
        budget_config = MagicMock()
        budget_config.scope = BudgetScope.CLUSTER
        mock_cluster.budget_types = {budget_type: budget_config}

        # Test successful validation
        node_service._validate_budget_config(mock_cluster, budget_type, None)
        # No exception raised means success

    async def test_validate_budget_config_not_found(self, node_service, mock_cluster):
        # Setup
        mock_cluster.budget_types = {}

        # Test budget type not found
        with pytest.raises(ObjectNotFound) as excinfo:
            node_service._validate_budget_config(mock_cluster, "non-existing-budget", None)
        assert "does not exists in the cluster" in str(excinfo.value)

    async def test_validate_budget_config_node_type_required(self, node_service, mock_cluster):
        # Setup
        budget_type = "test-budget"
        budget_config = MagicMock()
        budget_config.scope = BudgetScope.NODE_TYPE
        mock_cluster.budget_types = {budget_type: budget_config}

        # Test node type required but not provided
        with pytest.raises(ValueError) as excinfo:
            node_service._validate_budget_config(mock_cluster, budget_type, None)
        assert "requires `node_type` field" in str(excinfo.value)

    async def test_create_node_success(self, node_service, mock_cluster, mock_node, mock_node_out):
        # Setup
        request_data = CreateNodeRequest(
            cluster_id="test-cluster",
            budget_type="test-budget",
            node_type="test-node-type",
        )

        # Configure mocks
        node_config = NodeConfig()
        budget_config = MagicMock()
        budget_config.scope = BudgetScope.CLUSTER

        mock_cluster.budget_types = {"test-budget": budget_config}
        mock_cluster.get_node_type_config.return_value = node_config
        mock_cluster.create_node.return_value = mock_node

        # Patch NodeOut.from_node to return a valid NodeOut object
        with patch("golem_workers.models.NodeOut.from_node", return_value=mock_node_out):
            # Execute test
            response = await node_service.create_node(request_data)

            # Verify results
            assert isinstance(response, CreateNodeResponse)
            assert response.node == mock_node_out
            mock_cluster.create_node.assert_called_once()

    async def test_get_node_api_success(self, node_service, mock_cluster, mock_node, mock_node_out):
        # Setup
        mock_cluster.nodes = {"test-node-id": mock_node}

        # Patch NodeOut.from_node to return a valid NodeOut object
        with patch("golem_workers.models.NodeOut.from_node", return_value=mock_node_out):
            # Execute test
            response = await node_service.get_node("test-cluster", "test-node-id")

            # Verify results
            assert isinstance(response, GetNodeResponse)
            assert response.node == mock_node_out

    async def test_delete_node_success(self, node_service, mock_cluster, mock_node, mock_node_out):
        # Setup
        mock_cluster.nodes = {"test-node-id": mock_node}

        # Patch NodeOut.from_node to return a valid NodeOut object
        with patch("golem_workers.models.NodeOut.from_node", return_value=mock_node_out):
            # Execute test
            response = await node_service.delete_node("test-cluster", "test-node-id")

            # Verify results
            assert isinstance(response, DeleteNodeResponse)
            assert response.node == mock_node_out
            mock_cluster.delete_node.assert_called_once_with(mock_node)
