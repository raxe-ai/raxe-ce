"""Tests for customer CLI commands.

TDD: These tests define expected CLI behavior for customer management under MSSPs.
Implementation should make these tests pass.

Commands:
- raxe customer create --mssp <mssp_id> --id <id> --name <name>
- raxe customer list --mssp <mssp_id> [--output json|table]
- raxe customer show --mssp <mssp_id> <customer_id> [--output json|table]
- raxe customer configure <customer_id> --data-mode <mode> --data-fields <fields>
- raxe customer delete --mssp <mssp_id> <customer_id> [--force]
"""

import json

import pytest
from click.testing import CliRunner

from raxe.cli.customer import customer


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_mssp_path(tmp_path, monkeypatch):
    """Mock MSSP config path to use temp directory."""
    mssp_path = tmp_path / "mssp"
    mssp_path.mkdir()
    # Patch both infrastructure and application layer imports
    monkeypatch.setattr("raxe.infrastructure.mssp.get_mssp_base_path", lambda: mssp_path)
    monkeypatch.setattr("raxe.application.mssp_service.get_mssp_base_path", lambda: mssp_path)
    return mssp_path


@pytest.fixture
def setup_mssp(runner, mock_mssp_path):
    """Create an MSSP for customer tests."""
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
    return "mssp_partner"


class TestCustomerCreate:
    """Tests for raxe customer create command."""

    def test_create_customer_success(self, runner, mock_mssp_path, setup_mssp):
        """Test creating a customer successfully."""
        result = runner.invoke(
            customer,
            [
                "create",
                "--mssp",
                setup_mssp,
                "--id",
                "cust_acme",
                "--name",
                "Acme Corp",
            ],
        )

        assert result.exit_code == 0
        assert "cust_acme" in result.output or "Acme" in result.output

    def test_create_customer_validates_id_prefix(self, runner, mock_mssp_path, setup_mssp):
        """Test that customer ID must start with 'cust_'."""
        result = runner.invoke(
            customer,
            [
                "create",
                "--mssp",
                setup_mssp,
                "--id",
                "invalid_id",  # Missing cust_ prefix
                "--name",
                "Test Customer",
            ],
        )

        assert result.exit_code != 0
        assert "cust_" in result.output.lower() or "error" in result.output.lower()

    def test_create_customer_requires_existing_mssp(self, runner, mock_mssp_path):
        """Test that creating customer requires existing MSSP."""
        result = runner.invoke(
            customer,
            [
                "create",
                "--mssp",
                "mssp_nonexistent",
                "--id",
                "cust_test",
                "--name",
                "Test Customer",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_create_customer_duplicate_id_fails(self, runner, mock_mssp_path, setup_mssp):
        """Test that creating customer with duplicate ID fails."""
        # Create first
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )
        # Try duplicate
        result = runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Other Corp"],
        )

        assert result.exit_code != 0
        assert "already exists" in result.output.lower() or "error" in result.output.lower()

    def test_create_customer_with_data_mode(self, runner, mock_mssp_path, setup_mssp):
        """Test creating customer with specific data mode."""
        result = runner.invoke(
            customer,
            [
                "create",
                "--mssp",
                setup_mssp,
                "--id",
                "cust_acme",
                "--name",
                "Acme Corp",
                "--data-mode",
                "full",
            ],
        )

        assert result.exit_code == 0
        assert "full" in result.output.lower()

    def test_create_customer_default_data_mode_privacy_safe(
        self, runner, mock_mssp_path, setup_mssp
    ):
        """Test that default data mode is privacy_safe."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer, ["show", "--mssp", setup_mssp, "cust_acme", "--output", "json"]
        )

        data = json.loads(result.output)
        assert data.get("data_mode") == "privacy_safe"


class TestCustomerList:
    """Tests for raxe customer list command."""

    def test_list_customers_empty(self, runner, mock_mssp_path, setup_mssp):
        """Test listing customers when none exist."""
        result = runner.invoke(customer, ["list", "--mssp", setup_mssp])

        assert result.exit_code == 0
        assert "no customer" in result.output.lower() or "empty" in result.output.lower()

    def test_list_customers_with_data(self, runner, mock_mssp_path, setup_mssp):
        """Test listing customers with data."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(customer, ["list", "--mssp", setup_mssp])

        assert result.exit_code == 0
        assert "cust_acme" in result.output or "Acme" in result.output

    def test_list_customers_json_output(self, runner, mock_mssp_path, setup_mssp):
        """Test listing customers with JSON output."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(customer, ["list", "--mssp", setup_mssp, "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        if data:
            assert "customer_id" in data[0]


class TestCustomerShow:
    """Tests for raxe customer show command."""

    def test_show_customer_details(self, runner, mock_mssp_path, setup_mssp):
        """Test showing customer details."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(customer, ["show", "--mssp", setup_mssp, "cust_acme"])

        assert result.exit_code == 0
        assert "cust_acme" in result.output or "Acme" in result.output

    def test_show_nonexistent_customer(self, runner, mock_mssp_path, setup_mssp):
        """Test showing a customer that doesn't exist."""
        result = runner.invoke(customer, ["show", "--mssp", setup_mssp, "cust_nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_show_customer_json_output(self, runner, mock_mssp_path, setup_mssp):
        """Test showing customer with JSON output."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer, ["show", "--mssp", setup_mssp, "cust_acme", "--output", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["customer_id"] == "cust_acme"


class TestCustomerConfigure:
    """Tests for raxe customer configure command."""

    def test_configure_data_mode(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring customer data mode."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            ["configure", "--mssp", setup_mssp, "cust_acme", "--data-mode", "full"],
        )

        assert result.exit_code == 0
        assert "full" in result.output.lower()

    def test_configure_data_fields(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring customer data fields."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--data-fields",
                "prompt,response,matched_text",
            ],
        )

        assert result.exit_code == 0

    def test_configure_retention_days(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring customer retention days."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            ["configure", "--mssp", setup_mssp, "cust_acme", "--retention-days", "90"],
        )

        assert result.exit_code == 0
        assert "90" in result.output

    def test_configure_retention_days_validates_bounds(self, runner, mock_mssp_path, setup_mssp):
        """Test that retention days validates bounds (1-365)."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        # Try value too high
        result = runner.invoke(
            customer,
            ["configure", "--mssp", setup_mssp, "cust_acme", "--retention-days", "400"],
        )

        assert result.exit_code != 0
        assert "365" in result.output or "error" in result.output.lower()

    def test_configure_heartbeat_threshold(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring customer heartbeat threshold."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            ["configure", "--mssp", setup_mssp, "cust_acme", "--heartbeat-threshold", "600"],
        )

        assert result.exit_code == 0
        assert "600" in result.output


class TestCustomerDelete:
    """Tests for raxe customer delete command."""

    def test_delete_customer_success(self, runner, mock_mssp_path, setup_mssp):
        """Test deleting a customer successfully."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(customer, ["delete", "--mssp", setup_mssp, "cust_acme", "--force"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_nonexistent_customer(self, runner, mock_mssp_path, setup_mssp):
        """Test deleting a customer that doesn't exist."""
        result = runner.invoke(
            customer, ["delete", "--mssp", setup_mssp, "cust_nonexistent", "--force"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_delete_requires_force_or_confirmation(self, runner, mock_mssp_path, setup_mssp):
        """Test that delete requires --force or confirmation."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(customer, ["delete", "--mssp", setup_mssp, "cust_acme"], input="n\n")

        assert "abort" in result.output.lower() or result.exit_code == 1


class TestCustomerWebhookOverride:
    """Tests for customer-specific webhook override."""

    def test_configure_webhook_override(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring customer-specific webhook override."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--webhook-url",
                "https://acme.com/raxe/alerts",
                "--webhook-secret",
                "acme_secret",
            ],
        )

        assert result.exit_code == 0

    def test_webhook_override_requires_https(self, runner, mock_mssp_path, setup_mssp):
        """Test that webhook override requires HTTPS."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--webhook-url",
                "http://insecure.com/webhook",
                "--webhook-secret",
                "secret",
            ],
        )

        assert result.exit_code != 0
        assert "https" in result.output.lower() or "error" in result.output.lower()


class TestCustomerSIEMConfigure:
    """Tests for raxe customer siem configure command."""

    def test_configure_cef_http(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring CEF over HTTP."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "cef",
                "--url",
                "https://collector.example.com/cef",
                "--token",
                "test-token",
            ],
        )

        assert result.exit_code == 0
        assert "cef" in result.output.lower()

    def test_configure_cef_syslog_udp(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring CEF over Syslog UDP."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "cef",
                "--url",
                "syslog://siem.example.com",
                "--token",
                "not-used",
                "--transport",
                "udp",
                "--port",
                "514",
            ],
        )

        assert result.exit_code == 0
        assert "cef" in result.output.lower()

    def test_configure_cef_syslog_tcp_tls(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring CEF over Syslog TCP with TLS."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "cef",
                "--url",
                "syslog://siem.example.com",
                "--token",
                "not-used",
                "--transport",
                "tcp",
                "--port",
                "6514",
                "--tls",
            ],
        )

        assert result.exit_code == 0
        assert "cef" in result.output.lower()

    def test_configure_cef_with_facility(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring CEF with custom syslog facility."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "cef",
                "--url",
                "syslog://siem.example.com",
                "--token",
                "not-used",
                "--transport",
                "udp",
                "--facility",
                "17",
            ],
        )

        assert result.exit_code == 0

    def test_configure_arcsight(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring ArcSight SmartConnector."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "arcsight",
                "--url",
                "https://arcsight.example.com/receiver/v1/events",
                "--token",
                "test-token",
                "--smart-connector-id",
                "sc-001",
            ],
        )

        assert result.exit_code == 0
        assert "arcsight" in result.output.lower()

    def test_configure_arcsight_with_device_info(self, runner, mock_mssp_path, setup_mssp):
        """Test configuring ArcSight with custom device vendor/product."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "arcsight",
                "--url",
                "https://arcsight.example.com/receiver/v1/events",
                "--token",
                "test-token",
                "--device-vendor",
                "CustomVendor",
                "--device-product",
                "CustomProduct",
            ],
        )

        assert result.exit_code == 0

    def test_configure_cef_output_includes_type(self, runner, mock_mssp_path, setup_mssp):
        """Test that CEF configure output shows the SIEM type."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "cef",
                "--url",
                "https://collector.example.com/cef",
                "--token",
                "test-token",
            ],
        )

        assert result.exit_code == 0
        # Verify output shows the configured type
        assert "cef" in result.output.lower()
        assert "configured siem" in result.output.lower()

    def test_configure_arcsight_output_includes_type(self, runner, mock_mssp_path, setup_mssp):
        """Test that ArcSight configure output shows the SIEM type."""
        runner.invoke(
            customer,
            ["create", "--mssp", setup_mssp, "--id", "cust_acme", "--name", "Acme Corp"],
        )

        result = runner.invoke(
            customer,
            [
                "siem",
                "configure",
                "--mssp",
                setup_mssp,
                "cust_acme",
                "--type",
                "arcsight",
                "--url",
                "https://arcsight.example.com/receiver/v1/events",
                "--token",
                "test-token",
            ],
        )

        assert result.exit_code == 0
        # Verify output shows the configured type
        assert "arcsight" in result.output.lower()
        assert "configured siem" in result.output.lower()

    def test_help_output_shows_option_groups(self, runner):
        """Test that --help output displays grouped SIEM options."""
        result = runner.invoke(customer, ["siem", "configure", "--help"])

        assert result.exit_code == 0
        help_text = result.output
        # Verify all option group headers are present
        assert "Required SIEM Options" in help_text
        assert "General Options" in help_text
        assert "Splunk Options" in help_text
        assert "Azure Sentinel Options" in help_text
        assert "CrowdStrike LogScale Options" in help_text
        assert "CEF Transport Options" in help_text
        assert "ArcSight SmartConnector Options" in help_text

    def test_help_output_groups_options_under_correct_headers(self, runner):
        """Test that platform-specific options appear after their group header."""
        result = runner.invoke(customer, ["siem", "configure", "--help"])

        assert result.exit_code == 0
        help_text = result.output
        # Options should appear after their respective group header
        splunk_pos = help_text.index("Splunk Options")
        assert help_text.index("--index", splunk_pos) > splunk_pos
        assert help_text.index("--source", splunk_pos) > splunk_pos

        sentinel_pos = help_text.index("Azure Sentinel Options")
        assert help_text.index("--workspace-id", sentinel_pos) > sentinel_pos
        assert help_text.index("--log-type", sentinel_pos) > sentinel_pos

        cef_pos = help_text.index("CEF Transport Options")
        assert help_text.index("--transport", cef_pos) > cef_pos
        assert help_text.index("--tls", cef_pos) > cef_pos

        arcsight_pos = help_text.index("ArcSight SmartConnector Options")
        assert help_text.index("--smart-connector-id", arcsight_pos) > arcsight_pos
        assert help_text.index("--device-vendor", arcsight_pos) > arcsight_pos
