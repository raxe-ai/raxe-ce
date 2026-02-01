"""Tests for Partner API client."""

from pathlib import Path

import pytest

from raxe.application.mssp_service import CreateMSSPRequest, create_mssp_service
from raxe.infrastructure.mssp.yaml_repository import MSSPNotFoundError
from raxe.sdk.partner import PartnerClient, PartnerClientConfig
from raxe.sdk.partner.client import create_partner_client


@pytest.fixture
def mssp_test_dir(tmp_path: Path) -> Path:
    """Create temporary MSSP data directory."""
    mssp_dir = tmp_path / "mssp_data"
    mssp_dir.mkdir()
    return mssp_dir


@pytest.fixture
def test_mssp(mssp_test_dir: Path) -> str:
    """Create a test MSSP and return its ID."""
    service = create_mssp_service(base_path=mssp_test_dir)
    service.create_mssp(
        CreateMSSPRequest(
            mssp_id="mssp_test_partner",
            name="Test Partner MSSP",
            webhook_url="http://localhost:8080/webhook",
            webhook_secret="test_secret",
        )
    )
    return "mssp_test_partner"


class TestPartnerClientInit:
    """Tests for PartnerClient initialization."""

    def test_init_with_valid_mssp(self, mssp_test_dir: Path, test_mssp: str):
        """Test client initializes with valid MSSP."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        assert client.mssp_id == test_mssp
        assert client.mssp_name == "Test Partner MSSP"

    def test_init_with_nonexistent_mssp(self, mssp_test_dir: Path):
        """Test client raises error for nonexistent MSSP."""
        with pytest.raises(MSSPNotFoundError):
            PartnerClient(mssp_id="mssp_nonexistent", base_path=mssp_test_dir)

    def test_init_with_config(self, mssp_test_dir: Path, test_mssp: str):
        """Test client initializes with PartnerClientConfig."""
        config = PartnerClientConfig(
            mssp_id=test_mssp,
            base_path=mssp_test_dir,
        )
        client = PartnerClient(mssp_id=test_mssp, config=config)

        assert client.mssp_id == test_mssp

    def test_factory_function(self, mssp_test_dir: Path, test_mssp: str):
        """Test create_partner_client factory function."""
        client = create_partner_client(test_mssp, base_path=mssp_test_dir)

        assert isinstance(client, PartnerClient)
        assert client.mssp_id == test_mssp


class TestPartnerClientCustomers:
    """Tests for customer management methods."""

    def test_create_customer(self, mssp_test_dir: Path, test_mssp: str):
        """Test creating a customer."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        customer = client.create_customer(
            customer_id="cust_test",
            name="Test Customer",
            data_mode="full",
            data_fields=["prompt", "matched_text"],
        )

        assert customer.customer_id == "cust_test"
        assert customer.name == "Test Customer"
        assert customer.data_mode.value == "full"

    def test_list_customers(self, mssp_test_dir: Path, test_mssp: str):
        """Test listing customers."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        # Initially empty
        customers = client.list_customers()
        assert len(customers) == 0

        # Create some customers
        client.create_customer("cust_1", "Customer 1")
        client.create_customer("cust_2", "Customer 2")

        customers = client.list_customers()
        assert len(customers) == 2
        assert any(c.customer_id == "cust_1" for c in customers)
        assert any(c.customer_id == "cust_2" for c in customers)

    def test_get_customer(self, mssp_test_dir: Path, test_mssp: str):
        """Test getting a specific customer."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)
        client.create_customer("cust_get_test", "Get Test Customer")

        customer = client.get_customer("cust_get_test")

        assert customer.customer_id == "cust_get_test"
        assert customer.name == "Get Test Customer"

    def test_configure_customer(self, mssp_test_dir: Path, test_mssp: str):
        """Test configuring a customer."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)
        client.create_customer("cust_config", "Config Test", data_mode="privacy_safe")

        # Update configuration
        updated = client.configure_customer(
            "cust_config",
            data_mode="full",
            retention_days=60,
        )

        assert updated.data_mode.value == "full"
        assert updated.retention_days == 60

    def test_delete_customer(self, mssp_test_dir: Path, test_mssp: str):
        """Test deleting a customer."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)
        client.create_customer("cust_delete", "Delete Test")

        # Verify exists
        customer = client.get_customer("cust_delete")
        assert customer is not None

        # Delete
        client.delete_customer("cust_delete")

        # Verify deleted - returns None for non-existent customer
        deleted_customer = client.get_customer("cust_delete")
        assert deleted_customer is None

    def test_create_customer_with_privacy_safe(self, mssp_test_dir: Path, test_mssp: str):
        """Test creating customer with privacy_safe mode (default)."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        customer = client.create_customer(
            customer_id="cust_privacy",
            name="Privacy Safe Customer",
        )

        assert customer.data_mode.value == "privacy_safe"


class TestPartnerClientAgents:
    """Tests for agent management methods."""

    def test_list_agents_empty(self, mssp_test_dir: Path, test_mssp: str):
        """Test listing agents when none exist."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        agents = client.list_agents()

        # Should return empty list, not error
        assert agents == [] or isinstance(agents, list)

    def test_get_agent_nonexistent(self, mssp_test_dir: Path, test_mssp: str):
        """Test getting nonexistent agent."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        agent = client.get_agent("agent_nonexistent")

        assert agent is None


class TestPartnerClientStats:
    """Tests for statistics methods."""

    def test_get_mssp_stats(self, mssp_test_dir: Path, test_mssp: str):
        """Test getting MSSP-level statistics."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)

        # Create some customers
        client.create_customer("cust_stats_1", "Stats Customer 1")
        client.create_customer("cust_stats_2", "Stats Customer 2")

        stats = client.get_mssp_stats()

        assert stats["mssp_id"] == test_mssp
        assert stats["mssp_name"] == "Test Partner MSSP"
        assert stats["total_customers"] == 2
        assert "total_agents" in stats
        assert "online_agents" in stats

    def test_get_customer_stats(self, mssp_test_dir: Path, test_mssp: str):
        """Test getting customer-level statistics."""
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)
        client.create_customer("cust_stats_test", "Stats Test Customer")

        stats = client.get_customer_stats("cust_stats_test")

        assert stats["customer_id"] == "cust_stats_test"
        assert "total_agents" in stats
        assert "online_agents" in stats
        assert "total_scans" in stats


class TestPartnerClientWebhook:
    """Tests for webhook management."""

    def test_test_webhook_unreachable(self, mssp_test_dir: Path, test_mssp: str):
        """Test webhook test when webhook is unreachable."""
        # The test MSSP has a localhost webhook that isn't running
        client = PartnerClient(mssp_id=test_mssp, base_path=mssp_test_dir)
        result = client.test_webhook()

        # Should fail because the webhook server isn't running
        # This tests the error handling path
        assert result["success"] is False
        assert "webhook_url" in result
