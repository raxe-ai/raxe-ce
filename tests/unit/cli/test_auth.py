"""
Unit tests for the auth CLI commands.

Tests the authentication commands including:
- auth login
- auth status (local)
- auth status --remote
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.main import cli

# Correct path for patching RaxeConfig (imported inside auth_status function)
RAXE_CONFIG_PATH = "raxe.infrastructure.config.yaml_config.RaxeConfig"
# Path for patching check_health (imported inside _display_remote_status)
CHECK_HEALTH_PATH = "raxe.infrastructure.telemetry.health_client.check_health"


class TestAuthLogin:
    """Tests for auth login command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_auth_login_help(self, runner):
        """Test auth login help displays correctly."""
        result = runner.invoke(cli, ["auth", "login", "--help"])
        assert result.exit_code == 0
        assert "authentication URL" in result.output.lower() or "headless" in result.output.lower()

    def test_auth_login_prints_url(self, runner):
        """Test auth login prints URL for manual setup (no browser)."""
        result = runner.invoke(cli, ["auth", "login"])

        assert result.exit_code == 0
        # URL may be console.raxe.ai or console.beta.raxe.ai depending on env
        assert "console" in result.output and "raxe.ai" in result.output
        assert "raxe config set api_key" in result.output


class TestAuthStatus:
    """Tests for auth status command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_auth_status_help(self, runner):
        """Test auth status help displays correctly."""
        result = runner.invoke(cli, ["auth", "status", "--help"])
        assert result.exit_code == 0
        assert "authentication status" in result.output.lower()
        assert "--remote" in result.output

    @patch("raxe.infrastructure.telemetry.credential_store.CredentialStore")
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_no_key(self, mock_config_class, mock_cred_store_class, runner):
        """Test auth status when no API key is configured."""
        # Mock config with no API key
        mock_config = MagicMock()
        mock_config.core.api_key = ""
        mock_config_class.load.return_value = mock_config

        # Mock credential store with no credentials
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "No API key configured" in result.output

    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_live_key(self, mock_config_class, runner):
        """Test auth status with live key."""
        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config_class.load.return_value = mock_config

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Live" in result.output
        assert "raxe_live_ab" in result.output  # Masked key start

    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_temp_key(self, mock_config_class, runner):
        """Test auth status with temporary key."""
        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_temp_abc123def456ghi789jkl012mno345"
        mock_config_class.load.return_value = mock_config

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Temporary" in result.output
        # Either shows "14-day expiry" in type string or days remaining/expiry message
        assert (
            "14-day" in result.output.lower()
            or "days" in result.output.lower()
            or "expiry" in result.output.lower()
        )

    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_test_key(self, mock_config_class, runner):
        """Test auth status with test key."""
        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_test_abc123def456ghi789jkl012mno345"
        mock_config_class.load.return_value = mock_config

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Test" in result.output

    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_unknown_key(self, mock_config_class, runner):
        """Test auth status with unknown key format."""
        mock_config = MagicMock()
        mock_config.core.api_key = "invalid_key_format"
        mock_config_class.load.return_value = mock_config

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Unknown" in result.output

    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_shows_remote_hint(self, mock_config_class, runner):
        """Test auth status shows hint about --remote flag."""
        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config_class.load.return_value = mock_config

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "--remote" in result.output


class TestAuthStatusRemote:
    """Tests for auth status --remote command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_success(self, mock_config_class, mock_check_health, runner):
        """Test successful remote status check."""
        from raxe.infrastructure.telemetry.health_client import HealthResponse, TrialStatus

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_temp_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = "http://test.local/v1/telemetry"
        mock_config_class.load.return_value = mock_config

        mock_check_health.return_value = HealthResponse(
            key_type="temp",
            tier="temporary",
            days_remaining=7,
            events_today=5432,
            events_remaining=44568,
            rate_limit_rpm=50,
            rate_limit_daily=50000,
            can_disable_telemetry=False,
            offline_mode=False,
            server_time="2025-01-25T10:30:00.000Z",
            trial_status=TrialStatus(
                is_trial=True,
                days_remaining=7,
                scans_during_trial=5000,
                threats_detected_during_trial=150,
            ),
        )

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0
        assert "Remote" in result.output
        assert "Temporary" in result.output
        assert "7" in result.output  # Days remaining
        assert "5,432" in result.output  # Events sent
        assert "44,568" in result.output  # Events remaining
        assert "50" in result.output  # Rate limit RPM
        assert "50,000" in result.output  # Rate limit daily

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_live_key(self, mock_config_class, mock_check_health, runner):
        """Test remote status for live key."""
        from raxe.infrastructure.telemetry.health_client import HealthResponse

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = None  # Use default
        mock_config_class.load.return_value = mock_config

        mock_check_health.return_value = HealthResponse(
            key_type="live",
            tier="pro",
            days_remaining=None,
            events_today=10000,
            events_remaining=990000,
            rate_limit_rpm=500,
            rate_limit_daily=1000000,
            can_disable_telemetry=True,
            offline_mode=True,
            server_time="2025-01-25T10:30:00.000Z",
            trial_status=None,
        )

        result = runner.invoke(cli, ["auth", "status", "-r"])

        assert result.exit_code == 0
        assert "Live" in result.output
        assert "Pro" in result.output
        assert "Can Disable Telemetry" in result.output
        assert "Yes" in result.output  # Features enabled

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_auth_error(self, mock_config_class, mock_check_health, runner):
        """Test remote status with authentication error."""
        from raxe.infrastructure.telemetry.health_client import AuthenticationError

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_invalid_key_here_12345678"
        mock_config.telemetry.endpoint = None
        mock_config_class.load.return_value = mock_config

        mock_check_health.side_effect = AuthenticationError("Invalid API key")

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0  # Should not crash
        assert "Invalid" in result.output or "expired" in result.output.lower()
        # URL may be console.raxe.ai or console.beta.raxe.ai depending on env
        assert "console" in result.output and "raxe.ai" in result.output

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_network_error(self, mock_config_class, mock_check_health, runner):
        """Test remote status with network error falls back to local."""
        from raxe.infrastructure.telemetry.health_client import NetworkError

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = None
        mock_config_class.load.return_value = mock_config

        mock_check_health.side_effect = NetworkError("Could not reach server")

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0  # Should not crash
        assert "Could not reach server" in result.output
        # Should fall back to local status
        assert "local status" in result.output.lower()

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_timeout(self, mock_config_class, mock_check_health, runner):
        """Test remote status with timeout falls back to local."""
        from raxe.infrastructure.telemetry.health_client import (
            TimeoutError as HealthTimeoutError,
        )

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = None
        mock_config_class.load.return_value = mock_config

        mock_check_health.side_effect = HealthTimeoutError("Request timed out")

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0  # Should not crash
        assert "timeout" in result.output.lower()
        # Should fall back to local status
        assert "local status" in result.output.lower()

    @patch("raxe.infrastructure.telemetry.credential_store.CredentialStore")
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_no_key(self, mock_config_class, mock_cred_store_class, runner):
        """Test remote status when no API key is configured."""
        # Mock config with no API key
        mock_config = MagicMock()
        mock_config.core.api_key = ""
        mock_config_class.load.return_value = mock_config

        # Mock credential store with no credentials
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0
        assert "No API key configured" in result.output

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_auth_status_remote_trial_expiring_soon(
        self, mock_config_class, mock_check_health, runner
    ):
        """Test remote status shows warning for keys expiring soon."""
        from raxe.infrastructure.telemetry.health_client import HealthResponse, TrialStatus

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_temp_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = None
        mock_config_class.load.return_value = mock_config

        mock_check_health.return_value = HealthResponse(
            key_type="temp",
            tier="temporary",
            days_remaining=2,  # Expiring soon!
            events_today=100,
            events_remaining=49900,
            rate_limit_rpm=50,
            rate_limit_daily=50000,
            can_disable_telemetry=False,
            offline_mode=False,
            server_time="2025-01-25T10:30:00.000Z",
            trial_status=TrialStatus(
                is_trial=True,
                days_remaining=2,
                scans_during_trial=1000,
                threats_detected_during_trial=50,
            ),
        )

        result = runner.invoke(cli, ["auth", "status", "--remote"])

        assert result.exit_code == 0
        assert "2" in result.output  # Days remaining
        # Should show upgrade prompt
        assert "permanent key" in result.output.lower() or "Upgrade" in result.output


class TestAuthShortFlag:
    """Test short flag -r works for --remote."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch(CHECK_HEALTH_PATH)
    @patch(RAXE_CONFIG_PATH)
    def test_short_flag_r(self, mock_config_class, mock_check_health, runner):
        """Test -r short flag works."""
        from raxe.infrastructure.telemetry.health_client import HealthResponse

        mock_config = MagicMock()
        mock_config.core.api_key = "raxe_live_abc123def456ghi789jkl012mno345"
        mock_config.telemetry.endpoint = None
        mock_config_class.load.return_value = mock_config

        mock_check_health.return_value = HealthResponse(
            key_type="live",
            tier="pro",
            days_remaining=None,
            events_today=100,
            events_remaining=999900,
            rate_limit_rpm=500,
            rate_limit_daily=1000000,
            can_disable_telemetry=True,
            offline_mode=True,
            server_time="2025-01-25T10:30:00.000Z",
        )

        result = runner.invoke(cli, ["auth", "status", "-r"])

        assert result.exit_code == 0
        assert "Remote" in result.output


CREDENTIAL_STORE_PATH = "raxe.infrastructure.telemetry.credential_store.CredentialStore"
COMPUTE_KEY_ID_PATH = "raxe.infrastructure.telemetry.credential_store.compute_key_id"


class TestAuthConnect:
    """Tests for auth connect command (device flow)."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_auth_connect_help(self, runner):
        """Test auth connect help displays correctly."""
        result = runner.invoke(cli, ["auth", "connect", "--help"])
        assert result.exit_code == 0
        assert "Connect CLI to your RAXE account" in result.output

    @patch("raxe.cli.auth._create_cli_session")
    @patch("raxe.cli.auth.webbrowser.open")
    @patch("raxe.cli.auth._poll_cli_session")
    @patch("raxe.cli.auth._save_new_credentials")
    @patch(CREDENTIAL_STORE_PATH)
    def test_auth_connect_success(
        self,
        mock_cred_store_class,
        mock_save_creds,
        mock_poll,
        mock_webbrowser,
        mock_create_session,
        runner,
    ):
        """Test successful device flow authentication."""
        # Mock credential store
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        # Mock session creation
        mock_create_session.return_value = {
            "session_id": "sess_test123",
            "connect_url": "https://console.raxe.ai/connect?session=sess_test123",
            "events_count": 0,
        }

        # Mock polling - return completed status
        mock_poll.return_value = {
            "status": "completed",
            "api_key": "raxe_live_abc123def456ghi789jkl012mno345",
            "linked_events": 0,
            "user_email": "test@example.com",
        }

        result = runner.invoke(cli, ["auth", "connect"])

        assert result.exit_code == 0
        assert "CLI Connected Successfully" in result.output
        assert "test@example.com" in result.output
        mock_webbrowser.assert_called_once()
        mock_save_creds.assert_called_once()

    @patch("raxe.cli.auth._create_cli_session")
    @patch(CREDENTIAL_STORE_PATH)
    def test_auth_connect_session_creation_fails(
        self,
        mock_cred_store_class,
        mock_create_session,
        runner,
    ):
        """Test fallback when session creation fails."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        mock_create_session.side_effect = Exception("Network error")

        result = runner.invoke(cli, ["auth", "connect"])

        assert result.exit_code == 0  # Should not crash
        assert "Failed to create session" in result.output
        assert "manual authentication" in result.output.lower()
        # URL may be console.raxe.ai or console.beta.raxe.ai depending on env
        assert "console" in result.output and "raxe.ai" in result.output

    @patch("raxe.cli.auth._create_cli_session")
    @patch("raxe.cli.auth.webbrowser.open")
    @patch("raxe.cli.auth._poll_cli_session")
    @patch(CREDENTIAL_STORE_PATH)
    def test_auth_connect_session_expires(
        self,
        mock_cred_store_class,
        mock_poll,
        mock_webbrowser,
        mock_create_session,
        runner,
    ):
        """Test handling when session expires."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        mock_create_session.return_value = {
            "session_id": "sess_test123",
            "connect_url": "https://console.raxe.ai/connect?session=sess_test123",
            "events_count": 0,
        }

        mock_poll.return_value = {"status": "expired"}

        result = runner.invoke(cli, ["auth", "connect"])

        assert result.exit_code == 0
        assert "Session expired" in result.output or "expired" in result.output.lower()

    @patch("raxe.cli.auth._create_cli_session")
    @patch("raxe.cli.auth.webbrowser.open")
    @patch("raxe.cli.auth._poll_cli_session")
    @patch("raxe.cli.auth._save_new_credentials")
    @patch("raxe.cli.auth._get_current_key_id_from_telemetry")
    @patch(COMPUTE_KEY_ID_PATH)
    @patch(CREDENTIAL_STORE_PATH)
    def test_auth_connect_with_existing_temp_key(
        self,
        mock_cred_store_class,
        mock_compute_key_id,
        mock_get_key_id,
        mock_save_creds,
        mock_poll,
        mock_webbrowser,
        mock_create_session,
        runner,
    ):
        """Test connect flow with existing temp key shows events count."""
        # Mock credential store with existing credentials
        mock_credentials = MagicMock()
        mock_credentials.api_key = "raxe_temp_existing123456789012345678"
        mock_credentials.installation_id = "inst_abc123def456789"
        mock_store = MagicMock()
        mock_store.load.return_value = mock_credentials
        mock_cred_store_class.return_value = mock_store
        # Make telemetry return None so it falls through to compute_key_id
        mock_get_key_id.return_value = None
        mock_compute_key_id.return_value = "key_abc123def456"

        mock_create_session.return_value = {
            "session_id": "sess_test123",
            "connect_url": "https://console.raxe.ai/connect?session=sess_test123",
            "events_count": 150,
        }

        mock_poll.return_value = {
            "status": "completed",
            "api_key": "raxe_live_abc123def456ghi789jkl012mno345",
            "linked_scans": 150,
            "user_email": "test@example.com",
        }

        result = runner.invoke(cli, ["auth", "connect"])

        assert result.exit_code == 0
        assert "150" in result.output  # Scans count shown
        assert "Scans Linked" in result.output
        # Verify temp_key_id was passed to session creation
        mock_create_session.assert_called_once_with("key_abc123def456", "inst_abc123def456789")


class TestAuthDefaultFlow:
    """Tests for default auth flow (raxe auth without subcommand)."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch("raxe.cli.auth._create_cli_session")
    @patch(CREDENTIAL_STORE_PATH)
    def test_auth_without_subcommand_invokes_connect(
        self,
        mock_cred_store_class,
        mock_create_session,
        runner,
    ):
        """Test that 'raxe auth' without subcommand runs connect flow."""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_cred_store_class.return_value = mock_store

        mock_create_session.side_effect = Exception("Network error")

        result = runner.invoke(cli, ["auth"])

        # Should have tried to create session (connect flow)
        mock_create_session.assert_called_once()
        assert "Failed to create session" in result.output


class TestKeyUpgradeEventTrigger:
    """Tests for cli_connect conversion trigger in key upgrade events."""

    def test_cli_connect_conversion_trigger_valid(self):
        """Test that cli_connect is a valid conversion trigger."""
        from raxe.domain.telemetry.events import create_key_upgrade_event

        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            previous_key_id="key_abc123def456",
            new_key_id="key_xyz789ghijk",
            days_on_previous=5,
            conversion_trigger="cli_connect",
        )

        assert event.event_type == "key_upgrade"
        assert event.payload["conversion_trigger"] == "cli_connect"
        assert event.payload["previous_key_type"] == "temp"
        assert event.payload["new_key_type"] == "community"
