"""Tests for RAXE doctor CLI command.

Tests cover:
- All checks passing
- Missing config file
- Missing API key
- Rules check
- Performance check
- JSON export
- Quiet mode
- Auto-fix functionality
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.doctor import HealthCheck, doctor


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def _make_checks(statuses: list[str]) -> list[HealthCheck]:
    """Helper to build a list of HealthCheck objects."""
    names = [
        "Python Version",
        "RAXE Version",
        "Dependencies",
        "API Key Status",
        "Config File",
        "Config Valid",
        "Database File",
        "SQLite Version",
        "Database Size",
        "Rules Loaded",
        "Bundled Packs",
        "Avg Scan Time",
        "P95 Latency",
    ]
    checks = []
    for i, status in enumerate(statuses):
        name = names[i] if i < len(names) else f"Check {i}"
        checks.append(HealthCheck(name=name, status=status, message="test message"))
    return checks


class TestDoctorAllPass:
    """Tests for doctor command when all checks pass."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_all_checks_pass(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
    ):
        """Test doctor command when all checks pass."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(name="Config File", status="ok", message="Found"),
            HealthCheck(name="Config Valid", status="ok", message="Valid"),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        result = runner.invoke(doctor, [], obj={})

        assert result.exit_code == 0
        assert "passed" in result.output.lower() or "healthy" in result.output.lower()


class TestDoctorMissingConfig:
    """Tests for doctor command with missing configuration."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_missing_config(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
    ):
        """Test doctor reports missing config file."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(
                name="Config File",
                status="warning",
                message="Not found",
                fix_available=True,
            ),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        result = runner.invoke(doctor, [], obj={})

        assert result.exit_code == 0
        assert "warning" in result.output.lower() or "⚠" in result.output


class TestDoctorMissingApiKey:
    """Tests for doctor command with missing API key."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_missing_api_key(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
    ):
        """Test doctor reports API key issues."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(
                name="API Key Status",
                status="error",
                message="No API key configured",
                fix_available=True,
            ),
        ]
        mock_config.return_value = [
            HealthCheck(name="Config File", status="ok", message="Found"),
            HealthCheck(name="Config Valid", status="ok", message="Valid"),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        result = runner.invoke(doctor, [], obj={})

        assert result.exit_code == 0
        assert "error" in result.output.lower() or "❌" in result.output


class TestDoctorExport:
    """Tests for doctor --export functionality."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_export_report(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
        tmp_path,
    ):
        """Test exporting doctor report to file."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(name="Config File", status="ok", message="Found"),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        export_path = str(tmp_path / "report.txt")
        result = runner.invoke(doctor, ["--export", export_path], obj={})

        assert result.exit_code == 0
        assert Path(export_path).exists()

        content = Path(export_path).read_text()
        assert "Health Check Report" in content
        assert "Passed" in content


class TestDoctorFix:
    """Tests for doctor --fix functionality."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_fix_no_issues(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
    ):
        """Test --fix with no fixable issues."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(name="Config File", status="ok", message="Found"),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        result = runner.invoke(doctor, ["--fix"], obj={})

        assert result.exit_code == 0
        assert "no fixable" in result.output.lower() or "fix" in result.output.lower()

    @patch("raxe.cli.doctor._fix_config")
    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_fix_config_issue(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        mock_fix_config,
        runner,
    ):
        """Test --fix attempts to fix config issues."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(
                name="Config File",
                status="warning",
                message="Not found",
                fix_available=True,
            ),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        result = runner.invoke(doctor, ["--fix"], obj={})

        assert result.exit_code == 0
        mock_fix_config.assert_called_once()


class TestDoctorQuietMode:
    """Tests for quiet mode."""

    @patch("raxe.cli.doctor._check_performance")
    @patch("raxe.cli.doctor._check_rule_packs")
    @patch("raxe.cli.doctor._check_database")
    @patch("raxe.cli.doctor._check_configuration")
    @patch("raxe.cli.doctor._check_api_key")
    @patch("raxe.cli.doctor._check_installation")
    def test_doctor_quiet_mode_skips_logo(
        self,
        mock_install,
        mock_api,
        mock_config,
        mock_db,
        mock_rules,
        mock_perf,
        runner,
    ):
        """Test quiet mode suppresses logo."""
        mock_install.return_value = [
            HealthCheck(name="Python Version", status="ok", message="3.11.0"),
            HealthCheck(name="RAXE Version", status="ok", message="0.5.0"),
            HealthCheck(name="Dependencies", status="ok", message="All installed"),
        ]
        mock_api.return_value = [
            HealthCheck(name="API Key Status", status="ok", message="Valid"),
        ]
        mock_config.return_value = [
            HealthCheck(name="Config File", status="ok", message="Found"),
        ]
        mock_db.return_value = [
            HealthCheck(name="Database File", status="ok", message="Found"),
            HealthCheck(name="SQLite Version", status="ok", message="3.39.0"),
            HealthCheck(name="Database Size", status="ok", message="1.2 MB"),
        ]
        mock_rules.return_value = [
            HealthCheck(name="Rules Loaded", status="ok", message="515 rules"),
            HealthCheck(name="Bundled Packs", status="ok", message="Available"),
        ]
        mock_perf.return_value = [
            HealthCheck(name="Avg Scan Time", status="ok", message="4.2ms"),
            HealthCheck(name="P95 Latency", status="ok", message="8.1ms"),
        ]

        with patch("raxe.cli.branding.print_logo") as mock_logo:
            result = runner.invoke(doctor, [], obj={"quiet": True})

            assert result.exit_code == 0
            mock_logo.assert_not_called()


class TestHealthCheckModel:
    """Tests for HealthCheck dataclass."""

    def test_health_check_defaults(self):
        """Test HealthCheck default values."""
        check = HealthCheck(name="Test", status="ok", message="All good")
        assert check.details is None
        assert check.fix_available is False

    def test_health_check_with_fix(self):
        """Test HealthCheck with fix_available."""
        check = HealthCheck(
            name="Config",
            status="warning",
            message="Not found",
            details="Run raxe init",
            fix_available=True,
        )
        assert check.fix_available is True
        assert check.details == "Run raxe init"
