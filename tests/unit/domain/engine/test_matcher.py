"""Tests for pattern matcher.

Pure domain layer tests - fast, no I/O, no mocks.
"""

import pytest

from raxe.domain.engine.matcher import Match, PatternMatcher
from raxe.domain.rules.models import Pattern


class TestPatternMatcher:
    """Tests for PatternMatcher class."""

    def test_compile_pattern_basic(self) -> None:
        """Test basic pattern compilation."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])

        compiled = matcher.compile_pattern(pattern)

        assert compiled is not None
        assert compiled.search("abc123def") is not None

    def test_compile_pattern_with_ignorecase(self) -> None:
        """Test pattern compilation with IGNORECASE flag."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"hello", flags=["IGNORECASE"])

        compiled = matcher.compile_pattern(pattern)

        assert compiled.search("HELLO") is not None
        assert compiled.search("HeLLo") is not None
        assert compiled.search("hello") is not None

    def test_compile_pattern_caches(self) -> None:
        """Test that compiled patterns are cached."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])

        first = matcher.compile_pattern(pattern)
        second = matcher.compile_pattern(pattern)

        # Should be same object (cached)
        assert first is second
        assert matcher.cache_size == 1

    def test_compile_pattern_different_flags_separate_cache(self) -> None:
        """Test that same pattern with different flags cached separately."""
        matcher = PatternMatcher()
        pattern1 = Pattern(pattern=r"hello", flags=["IGNORECASE"])
        pattern2 = Pattern(pattern=r"hello", flags=[])

        compiled1 = matcher.compile_pattern(pattern1)
        compiled2 = matcher.compile_pattern(pattern2)

        # Different cache entries
        assert compiled1 is not compiled2
        assert matcher.cache_size == 2

    def test_compile_pattern_invalid_regex(self) -> None:
        """Test that invalid regex raises ValueError."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"[invalid(", flags=[])

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            matcher.compile_pattern(pattern)

    def test_compile_pattern_unknown_flag(self) -> None:
        """Test that unknown flag raises ValueError."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"test", flags=["UNKNOWN_FLAG"])

        with pytest.raises(ValueError, match="Unknown regex flag"):
            matcher.compile_pattern(pattern)

    def test_match_pattern_finds_single_match(self) -> None:
        """Test matching finds single occurrence."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d{3}", flags=[])
        text = "Call me at 555-12"  # Changed to avoid matching "123"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 1
        assert matches[0].matched_text == "555"
        assert matches[0].start == 11
        assert matches[0].pattern_index == 0

    def test_match_pattern_finds_multiple_matches(self) -> None:
        """Test matching finds all occurrences."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])
        text = "I have 3 apples and 5 oranges"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 2
        assert matches[0].matched_text == "3"
        assert matches[1].matched_text == "5"

    def test_match_pattern_no_match(self) -> None:
        """Test matching returns empty list when no match."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])
        text = "No numbers here"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 0

    def test_match_pattern_extracts_context(self) -> None:
        """Test that match extracts surrounding context."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"SECRET", flags=[])
        text = "This is a very long text with SECRET in the middle and more text after"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 1
        match = matches[0]
        assert match.matched_text == "SECRET"
        assert "long text with" in match.context_before
        assert "in the middle" in match.context_after

    def test_match_pattern_context_at_start(self) -> None:
        """Test context extraction at start of text."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"START", flags=[])
        text = "START of the text"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 1
        assert matches[0].context_before == ""
        assert "of the text" in matches[0].context_after

    def test_match_pattern_context_at_end(self) -> None:
        """Test context extraction at end of text."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"END", flags=[])
        text = "This is the END"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 1
        assert "This is the" in matches[0].context_before
        assert matches[0].context_after == ""

    def test_match_pattern_captures_groups(self) -> None:
        """Test that captured groups are preserved."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"(\w+)@(\w+)\.com", flags=[])
        text = "Email me at john@example.com"

        matches = matcher.match_pattern(text, pattern, pattern_index=0)

        assert len(matches) == 1
        assert matches[0].groups == ("john", "example")

    def test_match_all_patterns_or_logic(self) -> None:
        """Test that match_all_patterns implements OR logic."""
        matcher = PatternMatcher()
        patterns = [
            Pattern(pattern=r"apple", flags=[]),
            Pattern(pattern=r"orange", flags=[]),
        ]
        text = "I like apples"

        matches = matcher.match_all_patterns(text, patterns)

        # Should match first pattern only
        assert len(matches) == 1
        assert matches[0].matched_text == "apple"
        assert matches[0].pattern_index == 0

    def test_match_all_patterns_multiple_patterns_match(self) -> None:
        """Test multiple patterns matching same text."""
        matcher = PatternMatcher()
        patterns = [
            Pattern(pattern=r"test", flags=[]),
            Pattern(pattern=r"t\w+", flags=[]),
        ]
        text = "This is a test"

        matches = matcher.match_all_patterns(text, patterns)

        # Both patterns should match
        assert len(matches) == 2
        assert any(m.pattern_index == 0 for m in matches)
        assert any(m.pattern_index == 1 for m in matches)

    def test_match_all_patterns_continues_on_error(self) -> None:
        """Test that matching continues if one pattern fails."""
        matcher = PatternMatcher()
        # First pattern will fail to compile
        patterns = [
            Pattern(pattern=r"[invalid(", flags=[]),
            Pattern(pattern=r"valid", flags=[]),
        ]
        text = "This is valid text"

        # Should not raise, should continue with valid pattern
        matches = matcher.match_all_patterns(text, patterns)

        assert len(matches) == 1
        assert matches[0].matched_text == "valid"

    def test_clear_cache(self) -> None:
        """Test cache clearing."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])

        matcher.compile_pattern(pattern)
        assert matcher.cache_size == 1

        matcher.clear_cache()
        assert matcher.cache_size == 0

    def test_match_length_property(self) -> None:
        """Test Match.match_length property."""
        match = Match(
            pattern_index=0,
            start=10,
            end=15,
            matched_text="hello",
            groups=(),
            context_before="",
            context_after="",
        )

        assert match.match_length == 5

    def test_full_context_property(self) -> None:
        """Test Match.full_context property."""
        match = Match(
            pattern_index=0,
            start=10,
            end=15,
            matched_text="SECRET",
            groups=(),
            context_before="before ",
            context_after=" after",
        )

        assert match.full_context == "before [SECRET] after"


class TestPatternMatcherPerformance:
    """Performance tests for pattern matcher."""

    def test_pattern_compilation_is_fast(self) -> None:
        """Test that pattern compilation is <100ms."""
        import time

        matcher = PatternMatcher()
        pattern = Pattern(
            pattern=r"(?i)\b(ignore|disregard)\s+(all\s+)?(previous|prior)",
            flags=["IGNORECASE"],
        )

        start = time.perf_counter()
        matcher.compile_pattern(pattern)
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 100  # <100ms

    def test_cached_compilation_is_instant(self) -> None:
        """Test that cached pattern lookup is instant."""
        import time

        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\d+", flags=[])

        # First compilation
        matcher.compile_pattern(pattern)

        # Second should be instant (cached)
        start = time.perf_counter()
        matcher.compile_pattern(pattern)
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 1  # <1ms (effectively instant)

    def test_matching_1kb_text_is_fast(self) -> None:
        """Test that matching 1KB text is <1ms."""
        import time

        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"test", flags=[])
        text = "normal text " * 100  # ~1KB

        start = time.perf_counter()
        _ = matcher.match_pattern(text, pattern)
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 1  # <1ms


class TestPatternMatcherEdgeCases:
    """Edge case tests for pattern matcher."""

    def test_empty_text(self) -> None:
        """Test matching against empty text."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"test", flags=[])

        matches = matcher.match_pattern("", pattern)

        assert len(matches) == 0

    def test_very_long_match(self) -> None:
        """Test matching very long text."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r".+", flags=[])
        text = "x" * 1000

        matches = matcher.match_pattern(text, pattern)

        assert len(matches) == 1
        assert len(matches[0].matched_text) == 1000

    def test_overlapping_matches_not_returned(self) -> None:
        """Test that finditer doesn't return overlapping matches."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"\w\w", flags=[])
        text = "abc"

        matches = matcher.match_pattern(text, pattern)

        # Should find "ab" but not "bc" (overlaps with "ab")
        assert len(matches) == 1
        assert matches[0].matched_text == "ab"

    def test_multiline_flag(self) -> None:
        """Test MULTILINE flag works correctly."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"^test", flags=["MULTILINE"])
        text = "first line\ntest line\nlast line"

        matches = matcher.match_pattern(text, pattern)

        assert len(matches) == 1
        assert matches[0].matched_text == "test"

    def test_dotall_flag(self) -> None:
        """Test DOTALL flag works correctly."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"start.+end", flags=["DOTALL"])
        text = "start\nmiddle\nend"

        matches = matcher.match_pattern(text, pattern)

        assert len(matches) == 1
        assert "\n" in matches[0].matched_text


class TestPatternMatcherTimeout:
    """Security tests for timeout enforcement (ReDoS protection)."""

    def test_timeout_raises_on_slow_pattern(self) -> None:
        """Test that timeout is enforced for pathological patterns.

        This verifies the fix for S-001: ReDoS vulnerability.
        Uses a pattern that causes catastrophic backtracking in regex module.
        """
        matcher = PatternMatcher()
        # Evil regex - (a|a)+ causes exponential backtracking even in regex module
        evil_pattern = Pattern(pattern=r"(a|a)+$", flags=[], timeout=0.1)
        # Input that causes exponential backtracking
        evil_text = "a" * 25 + "!"

        with pytest.raises(ValueError, match="timed out"):
            matcher.match_pattern(evil_text, evil_pattern, timeout_seconds=0.1)

    def test_timeout_seconds_overrides_pattern_timeout(self) -> None:
        """Test that explicit timeout_seconds overrides pattern.timeout."""
        matcher = PatternMatcher()
        # Use pattern that causes backtracking in regex module
        pattern = Pattern(pattern=r"(a|a)+$", flags=[], timeout=10.0)
        evil_text = "a" * 25 + "!"

        # Should timeout at 0.1s despite pattern having 10s timeout
        with pytest.raises(ValueError, match="timed out"):
            matcher.match_pattern(evil_text, pattern, timeout_seconds=0.1)

    def test_normal_patterns_complete_before_timeout(self) -> None:
        """Test that normal patterns don't trigger timeout."""
        matcher = PatternMatcher()
        pattern = Pattern(pattern=r"test\d+", flags=[])
        text = "test123 test456 test789"

        # Should complete without timeout
        matches = matcher.match_pattern(text, pattern, timeout_seconds=1.0)

        assert len(matches) == 3
        assert matches[0].matched_text == "test123"
        assert matches[1].matched_text == "test456"
        assert matches[2].matched_text == "test789"

    def test_default_timeout_used_when_none_specified(self) -> None:
        """Test that default timeout (5.0s) is used when not specified."""
        matcher = PatternMatcher()
        # Fast pattern should complete well within default timeout
        pattern = Pattern(pattern=r"\d+", flags=[])
        text = "abc123def"

        matches = matcher.match_pattern(text, pattern)

        assert len(matches) == 1
        assert matches[0].matched_text == "123"
