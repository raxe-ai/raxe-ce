"""Unit tests for inline suppression domain module.

Tests the PURE domain logic for parsing and merging inline suppressions.
No I/O, no mocks needed.
"""

from datetime import datetime, timezone

import pytest

from raxe.domain.inline_suppression import (
    InlineSuppressionSpec,
    merge_suppressions,
    parse_inline_suppression,
    parse_inline_suppressions,
)
from raxe.domain.suppression import (
    Suppression,
    SuppressionAction,
    SuppressionValidationError,
)


class TestParseInlineSuppressionStringPatterns:
    """Tests for parsing string pattern specifications."""

    def test_simple_exact_pattern(self):
        """Test parsing simple exact rule ID."""
        supp = parse_inline_suppression("pi-001")

        assert supp.pattern == "pi-001"
        assert supp.action == SuppressionAction.SUPPRESS
        assert supp.reason == "Inline suppression"
        assert supp.created_by == "inline"
        assert supp.created_at is not None

    def test_wildcard_pattern(self):
        """Test parsing wildcard pattern."""
        supp = parse_inline_suppression("pi-*")

        assert supp.pattern == "pi-*"
        assert supp.action == SuppressionAction.SUPPRESS

    def test_partial_wildcard(self):
        """Test parsing partial wildcard pattern."""
        supp = parse_inline_suppression("jb-00*")

        assert supp.pattern == "jb-00*"

    def test_middle_wildcard(self):
        """Test parsing middle wildcard pattern."""
        supp = parse_inline_suppression("enc-*-base64")

        assert supp.pattern == "enc-*-base64"

    def test_all_valid_family_prefixes(self):
        """Test all valid family prefixes are accepted."""
        prefixes = ["pi", "jb", "pii", "cmd", "enc", "rag", "hc", "sec", "qual", "custom"]
        for prefix in prefixes:
            supp = parse_inline_suppression(f"{prefix}-*")
            assert supp.pattern == f"{prefix}-*"

    def test_bare_wildcard_raises(self):
        """Test bare wildcard raises validation error."""
        with pytest.raises(SuppressionValidationError, match="Bare wildcard"):
            parse_inline_suppression("*")

    def test_suffix_wildcard_raises(self):
        """Test suffix-only wildcard raises validation error."""
        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            parse_inline_suppression("*-injection")

    def test_unknown_prefix_with_wildcard_raises(self):
        """Test unknown family prefix with wildcard raises validation error."""
        with pytest.raises(SuppressionValidationError, match="Unknown family prefix"):
            parse_inline_suppression("unknown-*")


class TestParseInlineSuppressionDictPatterns:
    """Tests for parsing dict pattern specifications."""

    def test_dict_pattern_only(self):
        """Test dict with only pattern field."""
        supp = parse_inline_suppression({"pattern": "pi-001"})

        assert supp.pattern == "pi-001"
        assert supp.action == SuppressionAction.SUPPRESS
        assert supp.reason == "Inline suppression"

    def test_dict_with_suppress_action(self):
        """Test dict with SUPPRESS action."""
        supp = parse_inline_suppression(
            {"pattern": "pi-001", "action": "SUPPRESS", "reason": "Known FP"}
        )

        assert supp.action == SuppressionAction.SUPPRESS
        assert supp.reason == "Known FP"

    def test_dict_with_flag_action(self):
        """Test dict with FLAG action."""
        supp = parse_inline_suppression(
            {"pattern": "jb-*", "action": "FLAG", "reason": "Under investigation"}
        )

        assert supp.action == SuppressionAction.FLAG
        assert supp.reason == "Under investigation"

    def test_dict_with_log_action(self):
        """Test dict with LOG action."""
        supp = parse_inline_suppression(
            {"pattern": "enc-*", "action": "LOG", "reason": "Monitoring FP rate"}
        )

        assert supp.action == SuppressionAction.LOG
        assert supp.reason == "Monitoring FP rate"

    def test_dict_action_case_insensitive(self):
        """Test dict action is case insensitive."""
        lower = parse_inline_suppression({"pattern": "pi-001", "action": "flag"})
        upper = parse_inline_suppression({"pattern": "pi-001", "action": "FLAG"})
        mixed = parse_inline_suppression({"pattern": "pi-001", "action": "Flag"})

        assert lower.action == SuppressionAction.FLAG
        assert upper.action == SuppressionAction.FLAG
        assert mixed.action == SuppressionAction.FLAG

    def test_dict_with_enum_action(self):
        """Test dict accepts SuppressionAction enum directly."""
        supp = parse_inline_suppression({"pattern": "pi-001", "action": SuppressionAction.FLAG})

        assert supp.action == SuppressionAction.FLAG

    def test_dict_empty_reason_uses_default(self):
        """Test dict with empty reason uses default."""
        supp = parse_inline_suppression({"pattern": "pi-001", "reason": ""})

        assert supp.reason == "Inline suppression"

    def test_dict_missing_pattern_raises(self):
        """Test dict without pattern field raises error."""
        with pytest.raises(SuppressionValidationError, match="must have 'pattern' key"):
            parse_inline_suppression({"action": "SUPPRESS", "reason": "Test"})

    def test_dict_none_pattern_raises(self):
        """Test dict with None pattern raises error."""
        with pytest.raises(SuppressionValidationError, match="must have 'pattern' key"):
            parse_inline_suppression({"pattern": None})

    def test_dict_invalid_action_raises(self):
        """Test dict with invalid action raises error."""
        with pytest.raises(SuppressionValidationError, match="Invalid action"):
            parse_inline_suppression(
                {
                    "pattern": "pi-001",
                    "action": "BLOCK",  # Not a valid action
                }
            )


class TestParseInlineSuppressionInvalidTypes:
    """Tests for invalid input types."""

    def test_integer_raises(self):
        """Test integer input raises error."""
        with pytest.raises(SuppressionValidationError, match="Invalid inline suppression type"):
            parse_inline_suppression(123)  # type: ignore

    def test_list_raises(self):
        """Test list input raises error."""
        with pytest.raises(SuppressionValidationError, match="Invalid inline suppression type"):
            parse_inline_suppression(["pi-001"])  # type: ignore

    def test_none_raises(self):
        """Test None input raises error."""
        with pytest.raises(SuppressionValidationError):
            parse_inline_suppression(None)  # type: ignore


class TestParseInlineSuppressions:
    """Tests for parse_inline_suppressions function (list parsing)."""

    def test_empty_list(self):
        """Test empty list returns empty list."""
        result = parse_inline_suppressions([])
        assert result == []

    def test_none_returns_empty(self):
        """Test None input returns empty list."""
        result = parse_inline_suppressions(None)
        assert result == []

    def test_single_string(self):
        """Test single string in list."""
        result = parse_inline_suppressions(["pi-001"])

        assert len(result) == 1
        assert result[0].pattern == "pi-001"

    def test_multiple_strings(self):
        """Test multiple strings in list."""
        result = parse_inline_suppressions(["pi-001", "jb-*", "enc-001"])

        assert len(result) == 3
        patterns = [s.pattern for s in result]
        assert patterns == ["pi-001", "jb-*", "enc-001"]

    def test_single_dict(self):
        """Test single dict in list."""
        result = parse_inline_suppressions([{"pattern": "pi-001", "action": "FLAG"}])

        assert len(result) == 1
        assert result[0].action == SuppressionAction.FLAG

    def test_mixed_strings_and_dicts(self):
        """Test mixed strings and dicts in list."""
        specs: list[InlineSuppressionSpec] = [
            "pi-001",
            {"pattern": "jb-*", "action": "FLAG", "reason": "Review"},
            "enc-001",
            {"pattern": "pii-*", "action": "LOG"},
        ]
        result = parse_inline_suppressions(specs)

        assert len(result) == 4
        assert result[0].pattern == "pi-001"
        assert result[0].action == SuppressionAction.SUPPRESS
        assert result[1].pattern == "jb-*"
        assert result[1].action == SuppressionAction.FLAG
        assert result[2].pattern == "enc-001"
        assert result[2].action == SuppressionAction.SUPPRESS
        assert result[3].pattern == "pii-*"
        assert result[3].action == SuppressionAction.LOG

    def test_invalid_item_raises(self):
        """Test invalid item in list raises error."""
        with pytest.raises(SuppressionValidationError):
            parse_inline_suppressions(["pi-001", 123, "jb-*"])  # type: ignore

    def test_preserves_order(self):
        """Test list order is preserved."""
        specs = ["pi-003", "pi-001", "pi-002"]
        result = parse_inline_suppressions(specs)

        patterns = [s.pattern for s in result]
        assert patterns == ["pi-003", "pi-001", "pi-002"]


class TestMergeSuppressions:
    """Tests for merge_suppressions function."""

    def test_empty_both(self):
        """Test empty inputs returns empty."""
        result = merge_suppressions([], [])
        assert result == []

    def test_empty_config(self):
        """Test empty config with inline returns inline."""
        inline = [Suppression(pattern="pi-001", reason="Inline")]
        result = merge_suppressions([], inline)

        assert len(result) == 1
        assert result[0].reason == "Inline"

    def test_empty_inline(self):
        """Test empty inline with config returns config."""
        config = [Suppression(pattern="pi-001", reason="Config")]
        result = merge_suppressions(config, [])

        assert len(result) == 1
        assert result[0].reason == "Config"

    def test_inline_overrides_config_same_pattern(self):
        """Test inline suppression overrides config for same pattern."""
        config = [Suppression(pattern="pi-001", reason="Config", action=SuppressionAction.SUPPRESS)]
        inline = [Suppression(pattern="pi-001", reason="Inline", action=SuppressionAction.FLAG)]

        result = merge_suppressions(config, inline)

        assert len(result) == 1
        assert result[0].action == SuppressionAction.FLAG
        assert result[0].reason == "Inline"

    def test_merge_different_patterns(self):
        """Test merging different patterns combines them."""
        config = [Suppression(pattern="pi-001", reason="Config")]
        inline = [Suppression(pattern="jb-001", reason="Inline")]

        result = merge_suppressions(config, inline)

        assert len(result) == 2
        patterns = {s.pattern for s in result}
        assert patterns == {"pi-001", "jb-001"}

    def test_partial_override(self):
        """Test partial override with mixed patterns."""
        config = [
            Suppression(pattern="pi-001", reason="Config 1"),
            Suppression(pattern="pi-002", reason="Config 2"),
            Suppression(pattern="jb-001", reason="Config 3"),
        ]
        inline = [
            Suppression(pattern="pi-002", reason="Inline override", action=SuppressionAction.FLAG),
            Suppression(pattern="enc-001", reason="Inline new"),
        ]

        result = merge_suppressions(config, inline)

        assert len(result) == 4  # pi-001, pi-002 (overridden), jb-001, enc-001

        by_pattern = {s.pattern: s for s in result}
        assert by_pattern["pi-001"].reason == "Config 1"
        assert by_pattern["pi-002"].reason == "Inline override"
        assert by_pattern["pi-002"].action == SuppressionAction.FLAG
        assert by_pattern["jb-001"].reason == "Config 3"
        assert by_pattern["enc-001"].reason == "Inline new"

    def test_inline_order_matters(self):
        """Test later inline suppressions override earlier ones."""
        inline = [
            Suppression(pattern="pi-001", reason="First"),
            Suppression(pattern="pi-001", reason="Second"),
        ]

        result = merge_suppressions([], inline)

        assert len(result) == 1
        assert result[0].reason == "Second"


class TestSuppressionTimestamps:
    """Tests for suppression timestamp handling."""

    def test_created_at_is_set(self):
        """Test created_at is set on inline suppression."""
        before = datetime.now(timezone.utc).isoformat()
        supp = parse_inline_suppression("pi-001")
        after = datetime.now(timezone.utc).isoformat()

        assert supp.created_at is not None
        # Timestamp should be between before and after
        assert before <= supp.created_at <= after

    def test_created_by_is_inline(self):
        """Test created_by is set to 'inline'."""
        supp = parse_inline_suppression("pi-001")
        assert supp.created_by == "inline"

    def test_no_expires_at_by_default(self):
        """Test expires_at is not set by default."""
        supp = parse_inline_suppression("pi-001")
        assert supp.expires_at is None
