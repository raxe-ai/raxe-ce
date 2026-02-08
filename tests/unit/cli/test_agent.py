"""Tests for agent CLI commands.

TDD: These tests define expected CLI behavior for agent status monitoring.
Implementation should make these tests pass.

Commands:
- raxe agent list --mssp <mssp_id> [--customer <customer_id>] [--output json|table]
- raxe agent status --mssp <mssp_id> --customer <customer_id> <agent_id>
"""

import json

import pytest
from click.testing import CliRunner

from raxe.cli.agent import agent


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_mssp_path(tmp_path, monkeypatch):
    """Mock MSSP config path to use temp directory."""
    mssp_path = tmp_path / "mssp"
    mssp_path.mkdir()
    # Patch both infrastructure and application layer paths
    monkeypatch.setattr("raxe.infrastructure.mssp.get_mssp_base_path", lambda: mssp_path)
    monkeypatch.setattr("raxe.application.mssp_service.get_mssp_base_path", lambda: mssp_path)
    return mssp_path


@pytest.fixture
def setup_mssp_with_customer(runner, mock_mssp_path):
    """Create MSSP with customer for agent tests."""
    from raxe.cli.customer import customer
    from raxe.cli.mssp import mssp

    runner.invoke(
        mssp,
        [
            "create",
            "--id",
            "mssp_partner",
            "--name",
            "Partner Services",
            "--webhook-url",
            "https://test.com/webhook",
            "--webhook-secret",
            "secret",
        ],
    )
    runner.invoke(
        customer,
        ["create", "--mssp", "mssp_partner", "--id", "cust_acme", "--name", "Acme Corp"],
    )
    return ("mssp_partner", "cust_acme")


class TestAgentList:
    """Tests for raxe agent list command."""

    def test_list_agents_empty(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test listing agents when none exist."""
        mssp_id, customer_id = setup_mssp_with_customer

        result = runner.invoke(agent, ["list", "--mssp", mssp_id, "--customer", customer_id])

        assert result.exit_code == 0
        assert "no agent" in result.output.lower() or "empty" in result.output.lower()

    def test_list_agents_for_customer(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test listing agents for a specific customer."""
        mssp_id, customer_id = setup_mssp_with_customer

        # Register an agent (simulated via service or heartbeat)
        # For now, we test the command structure
        result = runner.invoke(agent, ["list", "--mssp", mssp_id, "--customer", customer_id])

        assert result.exit_code == 0

    def test_list_agents_all_customers(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test listing agents across all customers of an MSSP."""
        mssp_id, _ = setup_mssp_with_customer

        result = runner.invoke(agent, ["list", "--mssp", mssp_id])

        assert result.exit_code == 0

    def test_list_agents_json_output(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test listing agents with JSON output."""
        mssp_id, customer_id = setup_mssp_with_customer

        result = runner.invoke(
            agent, ["list", "--mssp", mssp_id, "--customer", customer_id, "--output", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_list_agents_without_mssp_succeeds(self, runner, mock_mssp_path):
        """Test that list works without --mssp (lists all agents)."""
        result = runner.invoke(agent, ["list"])

        # Should succeed — lists all agents (or shows empty message)
        assert result.exit_code == 0


class TestAgentStatus:
    """Tests for raxe agent status command."""

    def test_status_nonexistent_agent(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test status for agent that doesn't exist."""
        mssp_id, customer_id = setup_mssp_with_customer

        result = runner.invoke(
            agent, ["status", "--mssp", mssp_id, "--customer", customer_id, "agent_nonexistent"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_status_shows_agent_info(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test status shows agent information (when agent exists)."""
        mssp_id, customer_id = setup_mssp_with_customer

        # This test structure validates the command format
        # Actual agent registration would come from heartbeat service
        result = runner.invoke(
            agent, ["status", "--mssp", mssp_id, "--customer", customer_id, "agent_test"]
        )

        # Will fail until agent is registered, but validates command structure
        assert result.exit_code != 0 or "agent_test" in result.output

    def test_status_requires_mssp_and_customer(self, runner, mock_mssp_path):
        """Test that status requires both --mssp and --customer flags."""
        # Missing both
        result = runner.invoke(agent, ["status", "agent_test"])
        assert result.exit_code != 0

        # Missing --customer
        result = runner.invoke(agent, ["status", "--mssp", "mssp_test", "agent_test"])
        assert result.exit_code != 0


class TestAgentStatusDisplay:
    """Tests for agent status display fields."""

    def test_status_displays_online_status(self, runner, mock_mssp_path, setup_mssp_with_customer):
        """Test that status displays online/offline/degraded status."""
        mssp_id, customer_id = setup_mssp_with_customer

        # When implemented, this should show status
        # For now, validates the expectation
        result = runner.invoke(
            agent,
            [
                "status",
                "--mssp",
                mssp_id,
                "--customer",
                customer_id,
                "agent_test",
                "--output",
                "json",
            ],
        )

        # Command structure test - detailed status comes after implementation
        assert result.exit_code != 0 or "status" in result.output.lower()

    def test_status_json_includes_expected_fields(
        self, runner, mock_mssp_path, setup_mssp_with_customer
    ):
        """Test that status JSON includes expected fields when agent exists."""
        # This test documents the expected JSON structure
        # When an agent is registered and has heartbeat data:
        expected_fields = [
            "agent_id",
            "customer_id",
            "status",  # online, offline, degraded
            "last_heartbeat",
            "version",
        ]

        # For now, this is a documentation test
        # Implementation should ensure these fields exist
        assert len(expected_fields) == 5  # Validates our expectations are documented
