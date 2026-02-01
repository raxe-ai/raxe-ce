"""Tests for MSSP CLI commands.

TDD: These tests define expected CLI behavior for MSSP management.
Implementation should make these tests pass.

Commands:
- raxe mssp create --id <id> --name <name> --webhook-url <url> --webhook-secret <secret>
- raxe mssp list [--output json|table]
- raxe mssp show <id> [--output json|table]
- raxe mssp delete <id> [--force]
- raxe mssp test-webhook <id>
"""

import json

import pytest
from click.testing import CliRunner

from raxe.cli.mssp import mssp


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_mssp_path(tmp_path, monkeypatch):
    """Mock MSSP config path to use temp directory."""
    mssp_path = tmp_path / "mssp"
    mssp_path.mkdir()
    # Patch both infrastructure layer and application layer (where it's imported via 'from ... import')
    monkeypatch.setattr("raxe.infrastructure.mssp.get_mssp_base_path", lambda: mssp_path)
    monkeypatch.setattr("raxe.application.mssp_service.get_mssp_base_path", lambda: mssp_path)
    return mssp_path


class TestMSSPCreate:
    """Tests for raxe mssp create command."""

    def test_create_mssp_success(self, runner, mock_mssp_path):
        """Test creating an MSSP successfully."""
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "mssp_partner_net",
                "--name",
                "Partner Services Security",
                "--webhook-url",
                "https://soc.partnerco.com/raxe/alerts",
                "--webhook-secret",
                "test_secret_123",
            ],
        )

        assert result.exit_code == 0
        assert "mssp_partner_net" in result.output or "Partner Services" in result.output

    def test_create_mssp_validates_id_prefix(self, runner, mock_mssp_path):
        """Test that MSSP ID must start with 'mssp_'."""
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "invalid_id",  # Missing mssp_ prefix
                "--name",
                "Test MSSP",
                "--webhook-url",
                "https://test.com/webhook",
                "--webhook-secret",
                "secret",
            ],
        )

        assert result.exit_code != 0
        assert "mssp_" in result.output.lower() or "error" in result.output.lower()

    def test_create_mssp_requires_https_webhook(self, runner, mock_mssp_path):
        """Test that webhook URL must be HTTPS (except localhost)."""
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "mssp_test",
                "--name",
                "Test MSSP",
                "--webhook-url",
                "http://insecure.com/webhook",  # HTTP not HTTPS
                "--webhook-secret",
                "secret",
            ],
        )

        assert result.exit_code != 0
        assert "https" in result.output.lower() or "error" in result.output.lower()

    def test_create_mssp_allows_localhost_http(self, runner, mock_mssp_path):
        """Test that localhost HTTP is allowed for testing."""
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "mssp_test",
                "--name",
                "Test MSSP",
                "--webhook-url",
                "http://localhost:8080/webhook",
                "--webhook-secret",
                "secret",
            ],
        )

        assert result.exit_code == 0

    def test_create_mssp_duplicate_id_fails(self, runner, mock_mssp_path):
        """Test that creating MSSP with duplicate ID fails."""
        # Create first
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
        # Try duplicate
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "mssp_partner",
                "--name",
                "Other MSSP",
                "--webhook-url",
                "https://other.com/webhook",
                "--webhook-secret",
                "secret",
            ],
        )

        assert result.exit_code != 0
        assert "already exists" in result.output.lower() or "error" in result.output.lower()

    def test_create_mssp_with_tier(self, runner, mock_mssp_path):
        """Test creating MSSP with specific tier."""
        result = runner.invoke(
            mssp,
            [
                "create",
                "--id",
                "mssp_enterprise",
                "--name",
                "Enterprise MSSP",
                "--webhook-url",
                "https://test.com/webhook",
                "--webhook-secret",
                "secret",
                "--tier",
                "enterprise",
            ],
        )

        assert result.exit_code == 0
        assert "enterprise" in result.output.lower()


class TestMSSPList:
    """Tests for raxe mssp list command."""

    def test_list_mssp_empty(self, runner, mock_mssp_path):
        """Test listing MSSPs when none exist."""
        result = runner.invoke(mssp, ["list"])

        assert result.exit_code == 0
        assert "no mssp" in result.output.lower() or "empty" in result.output.lower()

    def test_list_mssp_with_data(self, runner, mock_mssp_path):
        """Test listing MSSPs with data."""
        # Create MSSP
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

        result = runner.invoke(mssp, ["list"])

        assert result.exit_code == 0
        assert "mssp_partner" in result.output or "Partner" in result.output

    def test_list_mssp_json_output(self, runner, mock_mssp_path):
        """Test listing MSSPs with JSON output."""
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

        result = runner.invoke(mssp, ["list", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        if data:
            assert "mssp_id" in data[0]


class TestMSSPShow:
    """Tests for raxe mssp show command."""

    def test_show_mssp_details(self, runner, mock_mssp_path):
        """Test showing MSSP details."""
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

        result = runner.invoke(mssp, ["show", "mssp_partner"])

        assert result.exit_code == 0
        assert "mssp_partner" in result.output or "Partner" in result.output

    def test_show_nonexistent_mssp(self, runner, mock_mssp_path):
        """Test showing an MSSP that doesn't exist."""
        result = runner.invoke(mssp, ["show", "mssp_nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_show_mssp_json_output(self, runner, mock_mssp_path):
        """Test showing MSSP with JSON output."""
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

        result = runner.invoke(mssp, ["show", "mssp_partner", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mssp_id"] == "mssp_partner"


class TestMSSPDelete:
    """Tests for raxe mssp delete command."""

    def test_delete_mssp_success(self, runner, mock_mssp_path):
        """Test deleting an MSSP successfully."""
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

        result = runner.invoke(mssp, ["delete", "mssp_partner", "--force"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_nonexistent_mssp(self, runner, mock_mssp_path):
        """Test deleting an MSSP that doesn't exist."""
        result = runner.invoke(mssp, ["delete", "mssp_nonexistent", "--force"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_delete_requires_force_or_confirmation(self, runner, mock_mssp_path):
        """Test that delete requires --force or confirmation."""
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

        result = runner.invoke(mssp, ["delete", "mssp_partner"], input="n\n")

        assert "abort" in result.output.lower() or result.exit_code == 1


class TestMSSPTestWebhook:
    """Tests for raxe mssp test-webhook command."""

    def test_test_webhook_sends_test_event(self, runner, mock_mssp_path, monkeypatch):
        """Test webhook test sends a test event."""
        from unittest.mock import MagicMock

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

        # Mock requests.post to return success
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr("requests.post", mock_post)

        result = runner.invoke(mssp, ["test-webhook", "mssp_partner"])

        assert result.exit_code == 0
        assert "success" in result.output.lower() or "✓" in result.output

    def test_test_webhook_reports_failure(self, runner, mock_mssp_path, monkeypatch):
        """Test webhook test reports failure properly."""
        from unittest.mock import MagicMock

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

        # Mock requests.post to return failure
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr("requests.post", mock_post)

        result = runner.invoke(mssp, ["test-webhook", "mssp_partner"])

        # Should report the failure
        assert (
            "fail" in result.output.lower()
            or "error" in result.output.lower()
            or "500" in result.output
        )
