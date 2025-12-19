"""Unit tests for suppression domain layer.

Tests for:
1. SuppressionAction enum
2. Suppression value object validation
3. Pattern matching with wildcards
4. Expiration logic
5. check_suppressions pure function
6. SuppressionCheckResult value object

All tests are PURE - no I/O, no mocks needed for domain logic.
"""
from datetime import datetime, timedelta, timezone

import pytest

from raxe.domain.suppression import (
    VALID_FAMILY_PREFIXES,
    Suppression,
    SuppressionAction,
    SuppressionCheckResult,
    SuppressionValidationError,
    check_suppressions,
)


class TestSuppressionAction:
    """Tests for SuppressionAction enum."""

    def test_suppress_value(self):
        """Test SUPPRESS action value."""
        assert SuppressionAction.SUPPRESS.value == "SUPPRESS"

    def test_flag_value(self):
        """Test FLAG action value."""
        assert SuppressionAction.FLAG.value == "FLAG"

    def test_log_value(self):
        """Test LOG action value."""
        assert SuppressionAction.LOG.value == "LOG"

    def test_all_actions_exist(self):
        """Test all expected actions exist."""
        actions = list(SuppressionAction)
        assert len(actions) == 3
        assert SuppressionAction.SUPPRESS in actions
        assert SuppressionAction.FLAG in actions
        assert SuppressionAction.LOG in actions


class TestSuppressionValidation:
    """Tests for Suppression validation."""

    def test_valid_exact_pattern(self):
        """Test valid exact pattern."""
        supp = Suppression(pattern="pi-001", reason="Test reason")
        assert supp.pattern == "pi-001"
        assert supp.reason == "Test reason"

    def test_valid_wildcard_prefix(self):
        """Test valid wildcard with family prefix."""
        supp = Suppression(pattern="pi-*", reason="Test reason")
        assert supp.pattern == "pi-*"

    def test_valid_wildcard_middle(self):
        """Test valid wildcard in middle of pattern."""
        supp = Suppression(pattern="jb-*-basic", reason="Test reason")
        assert supp.pattern == "jb-*-basic"

    def test_valid_wildcard_partial(self):
        """Test valid partial wildcard."""
        supp = Suppression(pattern="pi-00*", reason="Test reason")
        assert supp.pattern == "pi-00*"

    def test_empty_pattern_raises(self):
        """Test empty pattern raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="Pattern cannot be empty"):
            Suppression(pattern="", reason="Test reason")

    def test_bare_wildcard_raises(self):
        """Test bare wildcard '*' raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="Bare wildcard"):
            Suppression(pattern="*", reason="Test reason")

    def test_suffix_wildcard_raises(self):
        """Test suffix-only wildcard raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            Suppression(pattern="*-injection", reason="Test reason")

    def test_leading_wildcard_raises(self):
        """Test leading wildcard raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            Suppression(pattern="*pi-001", reason="Test reason")

    def test_unknown_family_prefix_raises(self):
        """Test unknown family prefix raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="Unknown family prefix"):
            Suppression(pattern="xyz-*", reason="Test reason")

    def test_empty_reason_raises(self):
        """Test empty reason raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="Reason cannot be empty"):
            Suppression(pattern="pi-001", reason="")

    def test_whitespace_only_reason_raises(self):
        """Test whitespace-only reason raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="Reason cannot be empty"):
            Suppression(pattern="pi-001", reason="   ")

    def test_invalid_expires_at_format_raises(self):
        """Test invalid expires_at format raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="expires_at must be valid ISO"):
            Suppression(pattern="pi-001", reason="Test", expires_at="not-a-date")

    def test_invalid_created_at_format_raises(self):
        """Test invalid created_at format raises SuppressionValidationError."""
        with pytest.raises(SuppressionValidationError, match="created_at must be valid ISO"):
            Suppression(pattern="pi-001", reason="Test", created_at="not-a-date")

    def test_valid_iso_dates(self):
        """Test valid ISO dates are accepted."""
        now = datetime.now(timezone.utc).isoformat()
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=now,
            expires_at=now,
        )
        assert supp.created_at == now
        assert supp.expires_at == now

    def test_default_action_is_suppress(self):
        """Test default action is SUPPRESS."""
        supp = Suppression(pattern="pi-001", reason="Test")
        assert supp.action == SuppressionAction.SUPPRESS

    def test_explicit_action_flag(self):
        """Test explicit FLAG action."""
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            action=SuppressionAction.FLAG,
        )
        assert supp.action == SuppressionAction.FLAG

    def test_explicit_action_log(self):
        """Test explicit LOG action."""
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            action=SuppressionAction.LOG,
        )
        assert supp.action == SuppressionAction.LOG


class TestValidFamilyPrefixes:
    """Tests for valid family prefixes constant."""

    def test_all_prefixes_exist(self):
        """Test all expected family prefixes are defined."""
        expected = {"pi", "jb", "pii", "cmd", "enc", "rag", "hc", "sec", "qual", "custom"}
        assert VALID_FAMILY_PREFIXES == expected

    @pytest.mark.parametrize("prefix", list(VALID_FAMILY_PREFIXES))
    def test_each_prefix_allows_wildcard(self, prefix):
        """Test each valid prefix allows wildcard patterns."""
        pattern = f"{prefix}-*"
        supp = Suppression(pattern=pattern, reason="Test")
        assert supp.pattern == pattern


class TestSuppressionMatching:
    """Tests for Suppression.matches() method."""

    def test_exact_match(self):
        """Test exact pattern match."""
        supp = Suppression(pattern="pi-001", reason="Test")
        assert supp.matches("pi-001")
        assert not supp.matches("pi-002")
        assert not supp.matches("jb-001")

    def test_wildcard_prefix_match(self):
        """Test wildcard prefix match (pi-*)."""
        supp = Suppression(pattern="pi-*", reason="Test")
        assert supp.matches("pi-001")
        assert supp.matches("pi-002")
        assert supp.matches("pi-advanced-001")
        assert not supp.matches("jb-001")
        assert not supp.matches("pii-email")

    def test_wildcard_middle_match(self):
        """Test wildcard in middle of pattern (jb-*-basic)."""
        supp = Suppression(pattern="jb-*-basic", reason="Test")
        assert supp.matches("jb-regex-basic")
        assert supp.matches("jb-pattern-basic")
        assert supp.matches("jb-x-basic")
        assert not supp.matches("jb-basic")
        assert not supp.matches("pi-regex-basic")

    def test_wildcard_partial_match(self):
        """Test partial wildcard match (pi-00*)."""
        supp = Suppression(pattern="pi-00*", reason="Test")
        assert supp.matches("pi-001")
        assert supp.matches("pi-002")
        assert supp.matches("pi-00x")
        assert not supp.matches("pi-010")
        assert not supp.matches("pi-1")

    def test_case_sensitive_matching(self):
        """Test matching is case-sensitive."""
        supp = Suppression(pattern="pi-001", reason="Test")
        assert supp.matches("pi-001")
        assert not supp.matches("PI-001")
        assert not supp.matches("Pi-001")


class TestSuppressionExpiration:
    """Tests for Suppression.is_expired() method."""

    def test_no_expiration(self):
        """Test suppression without expiration is never expired."""
        supp = Suppression(pattern="pi-001", reason="Test")
        assert not supp.is_expired()

    def test_future_expiration(self):
        """Test suppression with future expiration is not expired."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        supp = Suppression(pattern="pi-001", reason="Test", expires_at=future)
        assert not supp.is_expired()

    def test_past_expiration(self):
        """Test suppression with past expiration is expired."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        supp = Suppression(pattern="pi-001", reason="Test", expires_at=past)
        assert supp.is_expired()

    def test_expiration_with_mock_time(self):
        """Test expiration check with injected current time."""
        # Set expiration to a specific time
        expiry_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            expires_at=expiry_time.isoformat(),
        )

        # Before expiration
        before = datetime(2024, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
        assert not supp.is_expired(current_time=before)

        # After expiration
        after = datetime(2024, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
        assert supp.is_expired(current_time=after)

        # Exactly at expiration (not expired yet)
        at_expiry = expiry_time
        assert not supp.is_expired(current_time=at_expiry)

    def test_expiration_boundary(self):
        """Test expiration at exact boundary (1 second after)."""
        expiry_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            expires_at=expiry_time.isoformat(),
        )

        # 1 second before - not expired
        one_sec_before = expiry_time - timedelta(seconds=1)
        assert not supp.is_expired(current_time=one_sec_before)

        # 1 second after - expired
        one_sec_after = expiry_time + timedelta(seconds=1)
        assert supp.is_expired(current_time=one_sec_after)


class TestCheckSuppressionsFunction:
    """Tests for check_suppressions() pure function."""

    def test_no_suppressions(self):
        """Test with empty suppression list."""
        result = check_suppressions("pi-001", [])
        assert not result.is_suppressed
        assert result.action == SuppressionAction.SUPPRESS  # Default
        assert result.reason == ""
        assert result.matched_pattern == ""
        assert result.expired_matches == []

    def test_no_match(self):
        """Test when no suppression matches."""
        suppressions = [
            Suppression(pattern="pi-001", reason="Test 1"),
            Suppression(pattern="jb-*", reason="Test 2"),
        ]
        result = check_suppressions("pii-email", suppressions)
        assert not result.is_suppressed
        assert result.expired_matches == []

    def test_exact_match(self):
        """Test exact pattern match."""
        suppressions = [
            Suppression(pattern="pi-001", reason="Exact match test"),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.reason == "Exact match test"
        assert result.matched_pattern == "pi-001"
        assert result.action == SuppressionAction.SUPPRESS

    def test_wildcard_match(self):
        """Test wildcard pattern match."""
        suppressions = [
            Suppression(pattern="pi-*", reason="Wildcard test"),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.reason == "Wildcard test"
        assert result.matched_pattern == "pi-*"

    def test_first_match_wins(self):
        """Test that first matching suppression is used."""
        suppressions = [
            Suppression(pattern="pi-001", reason="Specific"),
            Suppression(pattern="pi-*", reason="Wildcard"),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.reason == "Specific"
        assert result.matched_pattern == "pi-001"

    def test_action_returned(self):
        """Test that action is returned from matching suppression."""
        suppressions = [
            Suppression(
                pattern="pi-001",
                reason="Flag test",
                action=SuppressionAction.FLAG,
            ),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.action == SuppressionAction.FLAG

    def test_expired_suppression_skipped(self):
        """Test that expired suppressions are skipped."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        suppressions = [
            Suppression(pattern="pi-001", reason="Expired", expires_at=past),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert not result.is_suppressed
        assert len(result.expired_matches) == 1
        assert result.expired_matches[0].pattern == "pi-001"

    def test_expired_tracked_before_active_match(self):
        """Test expired matches are tracked even when active match found."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        suppressions = [
            Suppression(pattern="pi-*", reason="Expired wildcard", expires_at=past),
            Suppression(pattern="pi-001", reason="Active exact"),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.reason == "Active exact"
        assert len(result.expired_matches) == 1
        assert result.expired_matches[0].reason == "Expired wildcard"

    def test_mock_time_for_expiration(self):
        """Test expiration with mock current time."""
        expiry = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        suppressions = [
            Suppression(
                pattern="pi-001",
                reason="Time-based",
                expires_at=expiry.isoformat(),
            ),
        ]

        # Before expiry - should match
        before = datetime(2024, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
        result = check_suppressions("pi-001", suppressions, current_time=before)
        assert result.is_suppressed
        assert result.expired_matches == []

        # After expiry - should not match
        after = datetime(2024, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = check_suppressions("pi-001", suppressions, current_time=after)
        assert not result.is_suppressed
        assert len(result.expired_matches) == 1


class TestSuppressionCheckResult:
    """Tests for SuppressionCheckResult value object."""

    def test_default_values(self):
        """Test default values for non-suppressed result."""
        result = SuppressionCheckResult(is_suppressed=False)
        assert not result.is_suppressed
        assert result.action == SuppressionAction.SUPPRESS
        assert result.reason == ""
        assert result.matched_pattern == ""
        assert result.expired_matches == []

    def test_suppressed_result(self):
        """Test suppressed result with all fields."""
        expired = Suppression(pattern="pi-*", reason="Expired")
        result = SuppressionCheckResult(
            is_suppressed=True,
            action=SuppressionAction.FLAG,
            reason="Test reason",
            matched_pattern="pi-001",
            expired_matches=[expired],
        )
        assert result.is_suppressed
        assert result.action == SuppressionAction.FLAG
        assert result.reason == "Test reason"
        assert result.matched_pattern == "pi-001"
        assert len(result.expired_matches) == 1

    def test_immutable(self):
        """Test that SuppressionCheckResult is immutable."""
        result = SuppressionCheckResult(is_suppressed=False)
        with pytest.raises(AttributeError):
            result.is_suppressed = True  # type: ignore


class TestSuppressionImmutability:
    """Tests for Suppression immutability."""

    def test_suppression_is_frozen(self):
        """Test that Suppression is immutable (frozen dataclass)."""
        supp = Suppression(pattern="pi-001", reason="Test")
        with pytest.raises(AttributeError):
            supp.pattern = "pi-002"  # type: ignore

    def test_suppression_hashable(self):
        """Test that Suppression is hashable (can be used in sets/dicts)."""
        supp1 = Suppression(pattern="pi-001", reason="Test")
        supp2 = Suppression(pattern="pi-001", reason="Test")

        # Same values should be equal
        assert supp1 == supp2

        # Can be added to set
        supp_set = {supp1, supp2}
        assert len(supp_set) == 1


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_pattern_at_max_length(self):
        """Test pattern at exactly maximum length is accepted."""
        from raxe.domain.suppression import MAX_PATTERN_LENGTH
        # Create pattern that is exactly at the limit (pi- prefix + remaining chars)
        pattern = "pi-" + "a" * (MAX_PATTERN_LENGTH - 3)
        assert len(pattern) == MAX_PATTERN_LENGTH
        supp = Suppression(pattern=pattern, reason="Max length pattern test")
        assert supp.pattern == pattern
        assert supp.matches(pattern)

    def test_reason_at_max_length(self):
        """Test reason at exactly maximum length is accepted."""
        from raxe.domain.suppression import MAX_REASON_LENGTH
        reason = "A" * MAX_REASON_LENGTH
        assert len(reason) == MAX_REASON_LENGTH
        supp = Suppression(pattern="pi-001", reason=reason)
        assert supp.reason == reason

    def test_special_characters_in_pattern(self):
        """Test special characters in pattern (non-wildcard)."""
        # Patterns with special regex chars should work with fnmatch
        supp = Suppression(pattern="pi-test_rule", reason="Test")
        assert supp.matches("pi-test_rule")
        assert not supp.matches("pi-test-rule")

    def test_unicode_in_reason(self):
        """Test Unicode characters in reason."""
        reason = "Test with unicode: \u2603 \u2764 \u2728"
        supp = Suppression(pattern="pi-001", reason=reason)
        assert supp.reason == reason

    def test_multiple_wildcards_in_pattern(self):
        """Test multiple wildcards in pattern."""
        supp = Suppression(pattern="pi-*-*", reason="Multi wildcard")
        assert supp.matches("pi-001-basic")
        assert supp.matches("pi-advanced-complex")
        assert not supp.matches("pi-001")

    def test_numeric_only_suffix(self):
        """Test pattern with numeric-only suffix."""
        supp = Suppression(pattern="pi-001", reason="Test")
        assert supp.matches("pi-001")
        assert not supp.matches("pi-1")
        assert not supp.matches("pi-0001")


class TestIntegrationWithActions:
    """Integration tests for action-based suppression handling."""

    def test_suppress_action_removes_detection(self):
        """Test SUPPRESS action semantic - detection should be removed."""
        suppressions = [
            Suppression(
                pattern="pi-001",
                reason="Known false positive",
                action=SuppressionAction.SUPPRESS,
            ),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.is_suppressed
        assert result.action == SuppressionAction.SUPPRESS
        # Application layer would remove this detection from results

    def test_flag_action_marks_detection(self):
        """Test FLAG action semantic - detection should be marked for review."""
        suppressions = [
            Suppression(
                pattern="pi-002",
                reason="Needs review",
                action=SuppressionAction.FLAG,
            ),
        ]
        result = check_suppressions("pi-002", suppressions)
        assert result.is_suppressed
        assert result.action == SuppressionAction.FLAG
        # Application layer would keep detection but mark it as flagged

    def test_log_action_tracks_detection(self):
        """Test LOG action semantic - detection should be logged only."""
        suppressions = [
            Suppression(
                pattern="pi-003",
                reason="Monitoring",
                action=SuppressionAction.LOG,
            ),
        ]
        result = check_suppressions("pi-003", suppressions)
        assert result.is_suppressed
        assert result.action == SuppressionAction.LOG
        # Application layer would keep detection and log it

    def test_mixed_actions_first_wins(self):
        """Test that first matching action wins in mixed list."""
        suppressions = [
            Suppression(pattern="pi-001", reason="Flag this", action=SuppressionAction.FLAG),
            Suppression(pattern="pi-*", reason="Suppress all", action=SuppressionAction.SUPPRESS),
        ]
        result = check_suppressions("pi-001", suppressions)
        assert result.action == SuppressionAction.FLAG
        assert result.reason == "Flag this"


# =============================================================================
# Security Hardening Tests
# =============================================================================


class TestSecurityLimits:
    """Tests for security hardening limits.

    These tests verify that security limits are enforced to prevent
    denial-of-service and resource exhaustion attacks.
    """

    def test_pattern_exceeds_max_length_raises_error(self):
        """Test that pattern exceeding MAX_PATTERN_LENGTH raises ValueError."""
        from raxe.domain.suppression import MAX_PATTERN_LENGTH

        # Pattern that exceeds the limit
        pattern = "pi-" + "a" * MAX_PATTERN_LENGTH  # 3 + MAX = exceeds limit
        assert len(pattern) > MAX_PATTERN_LENGTH

        with pytest.raises(
            SuppressionValidationError,
            match=f"Pattern exceeds maximum length of {MAX_PATTERN_LENGTH}",
        ):
            Suppression(pattern=pattern, reason="Test")

    def test_pattern_one_over_max_length_raises_error(self):
        """Test that pattern exactly 1 char over limit raises ValueError."""
        from raxe.domain.suppression import MAX_PATTERN_LENGTH

        # Pattern that is exactly 1 character over the limit
        pattern = "pi-" + "a" * (MAX_PATTERN_LENGTH - 2)  # 3 + (MAX-2) = MAX+1
        assert len(pattern) == MAX_PATTERN_LENGTH + 1

        with pytest.raises(
            SuppressionValidationError,
            match=f"Pattern exceeds maximum length of {MAX_PATTERN_LENGTH}",
        ):
            Suppression(pattern=pattern, reason="Test")

    def test_reason_exceeds_max_length_raises_error(self):
        """Test that reason exceeding MAX_REASON_LENGTH raises ValueError."""
        from raxe.domain.suppression import MAX_REASON_LENGTH

        # Reason that exceeds the limit
        reason = "A" * (MAX_REASON_LENGTH + 1)
        assert len(reason) > MAX_REASON_LENGTH

        with pytest.raises(
            SuppressionValidationError,
            match=f"Reason exceeds maximum length of {MAX_REASON_LENGTH}",
        ):
            Suppression(pattern="pi-001", reason=reason)

    def test_reason_one_over_max_length_raises_error(self):
        """Test that reason exactly 1 char over limit raises ValueError."""
        from raxe.domain.suppression import MAX_REASON_LENGTH

        reason = "A" * (MAX_REASON_LENGTH + 1)
        assert len(reason) == MAX_REASON_LENGTH + 1

        with pytest.raises(
            SuppressionValidationError,
            match=f"Reason exceeds maximum length of {MAX_REASON_LENGTH}",
        ):
            Suppression(pattern="pi-001", reason=reason)

    def test_security_limits_are_reasonable(self):
        """Test that security limits have reasonable values."""
        from raxe.domain.suppression import (
            MAX_PATTERN_LENGTH,
            MAX_REASON_LENGTH,
            MAX_SUPPRESSIONS,
        )

        # Pattern limit should allow reasonable patterns but prevent abuse
        assert MAX_PATTERN_LENGTH == 256
        assert MAX_PATTERN_LENGTH >= 50  # Must allow reasonable patterns
        assert MAX_PATTERN_LENGTH <= 1024  # Must prevent abuse

        # Reason limit should allow descriptive reasons but prevent abuse
        assert MAX_REASON_LENGTH == 500
        assert MAX_REASON_LENGTH >= 100  # Must allow descriptive reasons
        assert MAX_REASON_LENGTH <= 2048  # Must prevent abuse

        # Suppressions limit should allow reasonable usage but prevent DoS
        assert MAX_SUPPRESSIONS == 1000
        assert MAX_SUPPRESSIONS >= 100  # Must allow reasonable usage
        assert MAX_SUPPRESSIONS <= 10000  # Must prevent performance issues


class TestFailClosedExpiration:
    """Tests for fail-closed expiration behavior.

    Security: Invalid expiration dates should be treated as EXPIRED,
    not as valid/never-expiring, to prevent security bypasses.
    """

    def test_invalid_expiration_date_treated_as_expired(self):
        """Test that invalid expiration date is treated as expired (fail-closed)."""
        # We need to bypass __post_init__ validation to test is_expired directly
        # Use object.__setattr__ to set an invalid expires_at after construction
        supp = Suppression(pattern="pi-001", reason="Test")

        # Create a new suppression with invalid expires_at by bypassing validation
        # This simulates data loaded from storage that might have been corrupted
        from dataclasses import replace

        # We can't directly set invalid dates due to validation
        # Instead, test by creating a mock-like situation where we test the logic directly
        # The actual is_expired method should return True for invalid dates

        # For this test, we need to verify the code path that handles ValueError
        # Since __post_init__ prevents invalid dates, we test the behavior by
        # verifying that the code WOULD treat invalid dates as expired

        # The implementation now returns True for invalid dates (fail-closed)
        # We can verify this by checking the docstring behavior

        # Alternative: Use a custom Suppression subclass for testing
        class TestSuppression(Suppression):
            def __post_init__(self) -> None:
                # Skip validation to allow testing invalid dates
                pass

        test_supp = object.__new__(TestSuppression)
        object.__setattr__(test_supp, "pattern", "pi-001")
        object.__setattr__(test_supp, "reason", "Test")
        object.__setattr__(test_supp, "action", SuppressionAction.SUPPRESS)
        object.__setattr__(test_supp, "expires_at", "not-a-valid-date")
        object.__setattr__(test_supp, "created_at", None)
        object.__setattr__(test_supp, "created_by", None)

        # FAIL CLOSED: Invalid date should be treated as expired
        assert test_supp.is_expired() is True

    def test_malformed_date_formats_treated_as_expired(self):
        """Test various malformed date formats are all treated as expired."""

        class TestSuppression(Suppression):
            def __post_init__(self) -> None:
                pass  # Skip validation

        # Note: Empty string "" is treated as falsy (like None), meaning
        # "no expiration set" rather than "invalid date". This is intentional.
        malformed_dates = [
            "not-a-date",
            "2024-13-01",  # Invalid month
            "2024/12/31",  # Wrong separator
            "December 31, 2024",  # Wrong format
            "1234567890",  # Unix timestamp as string
            "null",
            "undefined",
        ]

        for bad_date in malformed_dates:
            test_supp = object.__new__(TestSuppression)
            object.__setattr__(test_supp, "pattern", "pi-001")
            object.__setattr__(test_supp, "reason", "Test")
            object.__setattr__(test_supp, "action", SuppressionAction.SUPPRESS)
            object.__setattr__(test_supp, "expires_at", bad_date)
            object.__setattr__(test_supp, "created_at", None)
            object.__setattr__(test_supp, "created_by", None)

            # FAIL CLOSED: All malformed dates should be treated as expired
            assert test_supp.is_expired() is True, f"Failed for date: {bad_date!r}"

    def test_empty_string_expiration_treated_as_no_expiration(self):
        """Test that empty string expiration is treated as no expiration (like None)."""

        class TestSuppression(Suppression):
            def __post_init__(self) -> None:
                pass  # Skip validation

        test_supp = object.__new__(TestSuppression)
        object.__setattr__(test_supp, "pattern", "pi-001")
        object.__setattr__(test_supp, "reason", "Test")
        object.__setattr__(test_supp, "action", SuppressionAction.SUPPRESS)
        object.__setattr__(test_supp, "expires_at", "")  # Empty string
        object.__setattr__(test_supp, "created_at", None)
        object.__setattr__(test_supp, "created_by", None)

        # Empty string is falsy, treated as "no expiration set"
        assert test_supp.is_expired() is False

    def test_naive_datetime_handled_correctly(self):
        """Test that naive (timezone-unaware) datetimes are handled correctly."""
        # Create a suppression with a naive datetime string
        # The implementation should treat it as UTC
        from datetime import datetime

        # Future naive datetime
        future_naive = datetime(2099, 12, 31, 23, 59, 59)
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            expires_at=future_naive.isoformat(),
        )

        # Should not be expired (future date)
        assert supp.is_expired() is False

    def test_timezone_aware_comparison(self):
        """Test that timezone-aware datetimes are compared correctly."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        supp = Suppression(pattern="pi-001", reason="Test", expires_at=future)

        # Should not be expired
        assert supp.is_expired() is False

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        supp_expired = Suppression(pattern="pi-002", reason="Test", expires_at=past)

        # Should be expired
        assert supp_expired.is_expired() is True
