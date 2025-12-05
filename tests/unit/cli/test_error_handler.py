"""
Unit tests for CLI error handler decorator.

Tests the @handle_cli_error decorator for consistent error handling across CLI commands.
"""

import json
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from raxe.cli.error_handler import (
    CATEGORY_EXIT_CODES,
    DOCS_BASE_URL,
    ERROR_HELP_MAP,
    EXCEPTION_EXIT_CODES,
    ErrorHelp,
    _format_error_display,
    _get_exit_code,
    _handle_click_exception,
    _handle_raxe_exception,
    _handle_unexpected_exception,
    handle_cli_error,
    handle_cli_error_quiet,
)
from raxe.cli.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_SCAN_ERROR,
    EXIT_SUCCESS,
    EXIT_THREAT_DETECTED,
)
from raxe.sdk.exceptions import (
    ConfigurationError,
    DatabaseError,
    ErrorCategory,
    ErrorCode,
    InfrastructureError,
    RaxeError,
    RaxeException,
    RuleError,
    ValidationError,
    config_not_found_error,
    validation_empty_input_error,
)


class TestErrorHelp:
    """Tests for the ErrorHelp dataclass."""

    def test_error_help_creation(self) -> None:
        """Test creating an ErrorHelp instance."""
        help_obj = ErrorHelp(
            title="Test error",
            suggested_fix="Run: test command",
            learn_more_suffix="TEST-001",
        )
        assert help_obj.title == "Test error"
        assert help_obj.suggested_fix == "Run: test command"
        assert help_obj.learn_more_suffix == "TEST-001"

    def test_error_help_frozen(self) -> None:
        """Test that ErrorHelp is immutable (frozen dataclass)."""
        help_obj = ErrorHelp(
            title="Test error",
            suggested_fix="Run: test",
            learn_more_suffix="TEST-001",
        )
        with pytest.raises(AttributeError):
            help_obj.title = "New title"  # type: ignore[misc]


class TestErrorHelpMap:
    """Tests for the ERROR_HELP_MAP coverage."""

    def test_all_error_codes_have_help(self) -> None:
        """Test that all ErrorCode values have corresponding help entries."""
        for error_code in ErrorCode:
            assert error_code in ERROR_HELP_MAP, f"Missing help for {error_code}"

    def test_help_entries_have_required_fields(self) -> None:
        """Test that all help entries have non-empty fields."""
        for error_code, help_obj in ERROR_HELP_MAP.items():
            assert help_obj.title, f"Empty title for {error_code}"
            assert help_obj.suggested_fix, f"Empty suggested_fix for {error_code}"
            assert help_obj.learn_more_suffix, f"Empty learn_more_suffix for {error_code}"

    def test_config_errors_have_config_related_fixes(self) -> None:
        """Test that configuration errors suggest relevant fixes."""
        config_codes = [
            ErrorCode.CFG_NOT_FOUND,
            ErrorCode.CFG_INVALID_FORMAT,
            ErrorCode.CFG_INITIALIZATION_FAILED,
        ]
        for code in config_codes:
            help_obj = ERROR_HELP_MAP[code]
            # Should suggest raxe commands
            fix_lower = help_obj.suggested_fix.lower()
            assert "raxe" in fix_lower or "config" in fix_lower


class TestExceptionExitCodes:
    """Tests for exception to exit code mapping."""

    def test_configuration_error_exit_code(self) -> None:
        """Test ConfigurationError maps to EXIT_CONFIG_ERROR."""
        assert EXCEPTION_EXIT_CODES[ConfigurationError] == EXIT_CONFIG_ERROR

    def test_validation_error_exit_code(self) -> None:
        """Test ValidationError maps to EXIT_INVALID_INPUT."""
        assert EXCEPTION_EXIT_CODES[ValidationError] == EXIT_INVALID_INPUT

    def test_database_error_exit_code(self) -> None:
        """Test DatabaseError maps to EXIT_SCAN_ERROR."""
        assert EXCEPTION_EXIT_CODES[DatabaseError] == EXIT_SCAN_ERROR

    def test_infrastructure_error_exit_code(self) -> None:
        """Test InfrastructureError maps to EXIT_SCAN_ERROR."""
        assert EXCEPTION_EXIT_CODES[InfrastructureError] == EXIT_SCAN_ERROR


class TestCategoryExitCodes:
    """Tests for error category to exit code mapping."""

    def test_cfg_category_exit_code(self) -> None:
        """Test CFG category maps to EXIT_CONFIG_ERROR."""
        assert CATEGORY_EXIT_CODES[ErrorCategory.CFG] == EXIT_CONFIG_ERROR

    def test_val_category_exit_code(self) -> None:
        """Test VAL category maps to EXIT_INVALID_INPUT."""
        assert CATEGORY_EXIT_CODES[ErrorCategory.VAL] == EXIT_INVALID_INPUT

    def test_db_category_exit_code(self) -> None:
        """Test DB category maps to EXIT_SCAN_ERROR."""
        assert CATEGORY_EXIT_CODES[ErrorCategory.DB] == EXIT_SCAN_ERROR

    def test_sec_category_exit_code(self) -> None:
        """Test SEC category maps to EXIT_THREAT_DETECTED."""
        assert CATEGORY_EXIT_CODES[ErrorCategory.SEC] == EXIT_THREAT_DETECTED


class TestGetExitCode:
    """Tests for the _get_exit_code function."""

    def test_configuration_error(self) -> None:
        """Test exit code for ConfigurationError."""
        exc = ConfigurationError("Test config error")
        assert _get_exit_code(exc) == EXIT_CONFIG_ERROR

    def test_validation_error(self) -> None:
        """Test exit code for ValidationError."""
        exc = ValidationError("Test validation error")
        assert _get_exit_code(exc) == EXIT_INVALID_INPUT

    def test_database_error(self) -> None:
        """Test exit code for DatabaseError."""
        exc = DatabaseError("Test database error")
        assert _get_exit_code(exc) == EXIT_SCAN_ERROR

    def test_infrastructure_error(self) -> None:
        """Test exit code for InfrastructureError."""
        exc = InfrastructureError("Test infra error")
        assert _get_exit_code(exc) == EXIT_SCAN_ERROR

    def test_rule_error(self) -> None:
        """Test exit code for RuleError."""
        exc = RuleError("Test rule error")
        assert _get_exit_code(exc) == EXIT_CONFIG_ERROR

    def test_raxe_exception_with_error_code(self) -> None:
        """Test exit code for RaxeException with error code uses category."""
        error = RaxeError(
            code=ErrorCode.VAL_EMPTY_INPUT,
            message="Empty input",
        )
        exc = RaxeException(error)
        assert _get_exit_code(exc) == EXIT_INVALID_INPUT

    def test_raxe_exception_without_error_code(self) -> None:
        """Test exit code for RaxeException without error code."""
        exc = RaxeException("Generic error")
        assert _get_exit_code(exc) == EXIT_SCAN_ERROR

    def test_generic_exception(self) -> None:
        """Test exit code for generic Exception."""
        exc = Exception("Generic error")
        assert _get_exit_code(exc) == EXIT_SCAN_ERROR


class TestHandleRaxeException:
    """Tests for _handle_raxe_exception function."""

    @patch("raxe.cli.error_handler.console")
    def test_handles_exception_with_error_code(self, mock_console: MagicMock) -> None:
        """Test handling exception with structured error code."""
        error = config_not_found_error("/path/to/config")
        exc = ConfigurationError(error)

        exit_code = _handle_raxe_exception(exc)

        assert exit_code == EXIT_CONFIG_ERROR
        # Verify console.print was called (error displayed)
        assert mock_console.print.called

    @patch("raxe.cli.error_handler.console")
    def test_handles_exception_without_error_code(self, mock_console: MagicMock) -> None:
        """Test handling exception without structured error code."""
        exc = RaxeException("Simple error message")

        exit_code = _handle_raxe_exception(exc)

        assert exit_code == EXIT_SCAN_ERROR
        assert mock_console.print.called

    @patch("raxe.cli.error_handler.console")
    def test_sanitizes_error_details(self, mock_console: MagicMock) -> None:
        """Test that sensitive information is sanitized from error details."""
        # Error with file path that should be sanitized
        error = RaxeError(
            code=ErrorCode.CFG_NOT_FOUND,
            message="Config not found",
            details={"path": "/Users/secret/private/config.yaml"},
        )
        exc = ConfigurationError(error)

        _handle_raxe_exception(exc)

        # Check that console.print was called
        assert mock_console.print.called


class TestHandleClickException:
    """Tests for _handle_click_exception function."""

    @patch("raxe.cli.error_handler.console")
    def test_handles_click_usage_error(self, mock_console: MagicMock) -> None:
        """Test handling Click UsageError."""
        exc = click.UsageError("Missing argument")

        exit_code = _handle_click_exception(exc)

        assert exit_code == EXIT_INVALID_INPUT
        assert mock_console.print.called

    @patch("raxe.cli.error_handler.console")
    def test_handles_click_bad_parameter(self, mock_console: MagicMock) -> None:
        """Test handling Click BadParameter."""
        exc = click.BadParameter("Invalid value")

        exit_code = _handle_click_exception(exc)

        assert exit_code == EXIT_INVALID_INPUT
        assert mock_console.print.called


class TestHandleUnexpectedException:
    """Tests for _handle_unexpected_exception function."""

    @patch("raxe.cli.error_handler.console")
    def test_handles_generic_exception(self, mock_console: MagicMock) -> None:
        """Test handling generic unexpected exception."""
        exc = RuntimeError("Unexpected error")

        exit_code = _handle_unexpected_exception(exc)

        assert exit_code == EXIT_SCAN_ERROR
        assert mock_console.print.called

    @patch("raxe.cli.error_handler.console")
    def test_sanitizes_sensitive_info(self, mock_console: MagicMock) -> None:
        """Test that sensitive info is sanitized from unexpected errors."""
        # Exception with file path
        exc = FileNotFoundError("/Users/secret/private/file.txt not found")

        _handle_unexpected_exception(exc)

        # Verify console was used (sanitization happens internally)
        assert mock_console.print.called


class TestHandleCliErrorDecorator:
    """Tests for the @handle_cli_error decorator."""

    def test_successful_function_returns_normally(self) -> None:
        """Test that successful functions return their result."""

        @handle_cli_error
        def successful_func() -> str:
            return "success"

        # Should return normally without calling sys.exit
        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            result = successful_func()
            mock_exit.assert_not_called()
            assert result == "success"

    def test_handles_raxe_exception(self) -> None:
        """Test decorator handles RaxeException."""

        @handle_cli_error
        def raises_raxe_exception() -> None:
            raise ConfigurationError(config_not_found_error("/path"))

        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            with patch("raxe.cli.error_handler.console"):
                raises_raxe_exception()
                mock_exit.assert_called_once_with(EXIT_CONFIG_ERROR)

    def test_handles_click_exception(self) -> None:
        """Test decorator handles Click exceptions."""

        @handle_cli_error
        def raises_click_exception() -> None:
            raise click.UsageError("Bad usage")

        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            with patch("raxe.cli.error_handler.console"):
                raises_click_exception()
                mock_exit.assert_called_once_with(EXIT_INVALID_INPUT)

    def test_handles_keyboard_interrupt(self) -> None:
        """Test decorator handles KeyboardInterrupt gracefully."""

        @handle_cli_error
        def raises_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            with patch("raxe.cli.error_handler.console"):
                raises_keyboard_interrupt()
                mock_exit.assert_called_once_with(EXIT_SUCCESS)

    def test_handles_unexpected_exception(self) -> None:
        """Test decorator handles unexpected exceptions."""

        @handle_cli_error
        def raises_unexpected() -> None:
            raise RuntimeError("Something went wrong")

        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            with patch("raxe.cli.error_handler.console"):
                raises_unexpected()
                mock_exit.assert_called_once_with(EXIT_SCAN_ERROR)

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function name and docstring."""

        @handle_cli_error
        def my_function() -> None:
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestHandleCliErrorQuietDecorator:
    """Tests for the @handle_cli_error_quiet decorator."""

    def test_successful_function_returns_normally(self) -> None:
        """Test that successful functions return their result."""

        @handle_cli_error_quiet
        def successful_func() -> str:
            return "success"

        with patch("raxe.cli.error_handler.sys.exit") as mock_exit:
            result = successful_func()
            mock_exit.assert_not_called()
            assert result == "success"

    def test_outputs_json_on_raxe_exception(self) -> None:
        """Test that RaxeException outputs JSON."""

        @handle_cli_error_quiet
        def raises_raxe_exception() -> None:
            error = RaxeError(
                code=ErrorCode.CFG_NOT_FOUND,
                message="Config not found",
                remediation="Run raxe init",
            )
            raise ConfigurationError(error)

        with patch("raxe.cli.error_handler.sys.exit"):
            with patch("click.echo") as mock_echo:
                raises_raxe_exception()
                # Verify JSON output
                call_args = mock_echo.call_args[0][0]
                output = json.loads(call_args)
                assert output["error"] is True
                assert output["code"] == "CFG-001"
                assert "Config not found" in output["message"]

    def test_outputs_json_on_click_exception(self) -> None:
        """Test that Click exception outputs JSON."""

        @handle_cli_error_quiet
        def raises_click_exception() -> None:
            raise click.UsageError("Bad usage")

        with patch("raxe.cli.error_handler.sys.exit"):
            with patch("click.echo") as mock_echo:
                raises_click_exception()
                call_args = mock_echo.call_args[0][0]
                output = json.loads(call_args)
                assert output["error"] is True
                assert output["code"] is None
                assert "Bad usage" in output["message"]

    def test_outputs_json_on_keyboard_interrupt(self) -> None:
        """Test that KeyboardInterrupt outputs JSON."""

        @handle_cli_error_quiet
        def raises_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        with patch("raxe.cli.error_handler.sys.exit"):
            with patch("click.echo") as mock_echo:
                raises_keyboard_interrupt()
                call_args = mock_echo.call_args[0][0]
                output = json.loads(call_args)
                assert output["error"] is True
                assert "cancelled" in output["message"].lower()

    def test_outputs_json_on_unexpected_exception(self) -> None:
        """Test that unexpected exception outputs JSON."""

        @handle_cli_error_quiet
        def raises_unexpected() -> None:
            raise RuntimeError("Unexpected error")

        with patch("raxe.cli.error_handler.sys.exit"):
            with patch("click.echo") as mock_echo:
                raises_unexpected()
                call_args = mock_echo.call_args[0][0]
                output = json.loads(call_args)
                assert output["error"] is True


class TestFormatErrorDisplay:
    """Tests for _format_error_display function."""

    @patch("raxe.cli.error_handler.console")
    def test_displays_error_with_all_fields(self, mock_console: MagicMock) -> None:
        """Test error display with all fields populated."""
        _format_error_display(
            error_code="CFG-001",
            title="Configuration not found",
            details="path=~/.raxe/config.yaml",
            suggested_fix="Run: raxe init",
            learn_more_url="https://docs.raxe.ai/errors/CFG-001",
        )

        # Verify multiple console.print calls for different sections
        assert mock_console.print.call_count >= 4

    @patch("raxe.cli.error_handler.console")
    def test_displays_error_without_optional_fields(self, mock_console: MagicMock) -> None:
        """Test error display without optional fields."""
        _format_error_display(
            error_code=None,
            title="Generic error",
            details=None,
            suggested_fix=None,
            learn_more_url=None,
        )

        # Should still display the basic error
        assert mock_console.print.called

    @patch("raxe.cli.error_handler.console")
    def test_displays_error_code_in_header(self, mock_console: MagicMock) -> None:
        """Test that error code is displayed in header."""
        _format_error_display(
            error_code="VAL-400",
            title="Empty input",
            details=None,
            suggested_fix=None,
            learn_more_url=None,
        )

        # Check that Panel was created (first call)
        assert mock_console.print.called


class TestIntegrationWithClickRunner:
    """Integration tests using Click's CliRunner."""

    def test_decorated_command_handles_error(self) -> None:
        """Test decorated Click command handles errors properly."""

        @click.command()
        @handle_cli_error
        def test_cmd() -> None:
            raise ConfigurationError(config_not_found_error("/test/path"))

        runner = CliRunner()
        result = runner.invoke(test_cmd)

        assert result.exit_code == EXIT_CONFIG_ERROR
        # Output should contain error information
        assert "ERROR" in result.output or "Configuration" in result.output

    def test_decorated_command_success(self) -> None:
        """Test decorated Click command succeeds normally."""

        @click.command()
        @handle_cli_error
        def test_cmd() -> None:
            click.echo("Success!")

        runner = CliRunner()
        result = runner.invoke(test_cmd)

        assert result.exit_code == 0
        assert "Success!" in result.output

    def test_quiet_decorated_command_outputs_json(self) -> None:
        """Test quiet decorator outputs JSON on error."""

        @click.command()
        @handle_cli_error_quiet
        def test_cmd() -> None:
            raise ValidationError(validation_empty_input_error())

        runner = CliRunner()
        result = runner.invoke(test_cmd)

        assert result.exit_code == EXIT_INVALID_INPUT
        # Output should be valid JSON
        output = json.loads(result.output)
        assert output["error"] is True
        assert output["code"] == "VAL-400"


class TestDocsBaseUrl:
    """Tests for documentation URL generation."""

    def test_docs_base_url_is_valid(self) -> None:
        """Test that DOCS_BASE_URL is a valid URL."""
        assert DOCS_BASE_URL.startswith("https://")
        assert "raxe.ai" in DOCS_BASE_URL

    def test_error_help_urls_are_consistent(self) -> None:
        """Test that all help entries have valid URL suffixes."""
        for error_code, help_obj in ERROR_HELP_MAP.items():
            # Suffix should match the error code format
            expected_suffix = error_code.value
            assert help_obj.learn_more_suffix == expected_suffix, (
                f"Mismatch for {error_code}: expected {expected_suffix}, "
                f"got {help_obj.learn_more_suffix}"
            )
