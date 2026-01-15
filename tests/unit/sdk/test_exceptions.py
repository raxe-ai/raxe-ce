"""Tests for RAXE SDK exceptions.

Tests the custom exception hierarchy used by the SDK.
"""

from unittest.mock import Mock

import pytest

from raxe.sdk.exceptions import (
    RaxeBlockedError,
    RaxeException,
    SecurityException,
)


class TestRaxeException:
    """Test base RaxeException."""

    def test_is_exception(self):
        """Test RaxeException is a standard exception."""
        exc = RaxeException("test error")
        assert isinstance(exc, Exception)

    def test_can_be_raised(self):
        """Test RaxeException can be raised and caught."""
        with pytest.raises(RaxeException) as exc_info:
            raise RaxeException("test message")

        assert "test message" in str(exc_info.value)

    def test_can_catch_subclasses(self):
        """Test catching RaxeException catches all subclasses."""
        with pytest.raises(RaxeException):
            raise SecurityException(Mock())


class TestSecurityException:
    """Test SecurityException."""

    def test_requires_result(self):
        """Test SecurityException requires result parameter."""
        mock_result = Mock()
        mock_result.severity = "HIGH"
        mock_result.total_detections = 3

        exc = SecurityException(mock_result)

        assert exc.result is mock_result

    def test_message_includes_severity(self):
        """Test exception message includes severity."""
        mock_result = Mock()
        mock_result.severity = "CRITICAL"
        mock_result.total_detections = 1

        exc = SecurityException(mock_result)
        message = str(exc)

        assert "Security threat detected" in message
        assert "CRITICAL" in message

    def test_message_includes_detection_count(self):
        """Test exception message includes detection count."""
        mock_result = Mock()
        mock_result.severity = "HIGH"
        mock_result.total_detections = 5

        exc = SecurityException(mock_result)
        message = str(exc)

        assert "5 detection(s)" in message

    def test_is_raxe_exception(self):
        """Test SecurityException inherits from RaxeException."""
        exc = SecurityException(Mock())
        assert isinstance(exc, RaxeException)


class TestRaxeBlockedError:
    """Test RaxeBlockedError."""

    def test_is_security_exception(self):
        """Test RaxeBlockedError inherits from SecurityException."""
        exc = RaxeBlockedError(Mock())
        assert isinstance(exc, SecurityException)
        assert isinstance(exc, RaxeException)

    def test_message_includes_policy(self):
        """Test exception message includes policy decision."""
        mock_result = Mock()
        mock_result.severity = "CRITICAL"
        mock_result.total_detections = 2
        mock_result.policy_decision = "BLOCK"

        exc = RaxeBlockedError(mock_result)
        message = str(exc)

        assert "Request blocked by policy" in message
        assert "BLOCK" in message

    def test_has_result_attribute(self):
        """Test RaxeBlockedError has result attribute."""
        mock_result = Mock()
        mock_result.severity = "HIGH"
        mock_result.total_detections = 1
        mock_result.policy_decision = "BLOCK"

        exc = RaxeBlockedError(mock_result)

        assert exc.result is mock_result
