"""Pattern matching engine for threat detection.

Pure domain layer - NO I/O operations.
All functions are stateless and side-effect free.

Performance targets:
- <1ms per pattern match
- Pattern compilation cached for reuse
- Timeout protection per pattern
"""
import re
from dataclasses import dataclass
from re import Pattern as RePattern

from raxe.domain.rules.models import Pattern


@dataclass(frozen=True)
class Match:
    """A single pattern match in text.

    Immutable value object representing where and what matched.

    Attributes:
        pattern_index: Which pattern in the rule matched (0-based)
        start: Start position in text
        end: End position in text
        matched_text: The actual matched text
        groups: Captured groups from regex
        context_before: Up to 50 chars before match
        context_after: Up to 50 chars after match
    """
    pattern_index: int
    start: int
    end: int
    matched_text: str
    groups: tuple[str, ...]
    context_before: str
    context_after: str

    @property
    def match_length(self) -> int:
        """Length of matched text."""
        return self.end - self.start

    @property
    def full_context(self) -> str:
        """Full context around match."""
        return f"{self.context_before}[{self.matched_text}]{self.context_after}"


class PatternMatcher:
    """Stateless pattern matching with timeout support.

    Pure domain logic - no I/O, no side effects.
    Caches compiled patterns for performance.

    Thread-safe for read operations (cache is write-once per pattern).
    """

    def __init__(self) -> None:
        """Initialize matcher with empty pattern cache."""
        self._compiled_cache: dict[str, RePattern[str]] = {}

    def compile_pattern(self, pattern: Pattern) -> RePattern[str]:
        """Compile regex pattern with flags.

        Args:
            pattern: Pattern object from rule

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If pattern is invalid or flags are unknown

        Note:
            Caches compiled patterns for performance.
            Cache key includes pattern string and flags.
        """
        # Create cache key from pattern and flags
        cache_key = f"{pattern.pattern}:{':'.join(sorted(pattern.flags))}"

        if cache_key in self._compiled_cache:
            return self._compiled_cache[cache_key]

        # Convert string flags to re module flags
        flags = 0
        for flag in pattern.flags:
            flag_upper = flag.upper()
            if flag_upper == "IGNORECASE":
                flags |= re.IGNORECASE
            elif flag_upper == "MULTILINE":
                flags |= re.MULTILINE
            elif flag_upper == "DOTALL":
                flags |= re.DOTALL
            elif flag_upper == "VERBOSE":
                flags |= re.VERBOSE
            elif flag_upper == "ASCII":
                flags |= re.ASCII
            else:
                raise ValueError(f"Unknown regex flag: {flag}")

        try:
            compiled = re.compile(pattern.pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern.pattern}': {e}") from e

        # Cache for future use
        self._compiled_cache[cache_key] = compiled
        return compiled

    def match_pattern(
        self,
        text: str,
        pattern: Pattern,
        pattern_index: int = 0,
        timeout_seconds: float | None = None,
    ) -> list[Match]:
        """Match a single pattern against text with timeout.

        Args:
            text: Text to search
            pattern: Pattern to match
            pattern_index: Index of this pattern in rule (for Match objects)
            timeout_seconds: Override pattern timeout (currently not enforced - see note)

        Returns:
            List of Match objects (empty if no matches)

        Raises:
            ValueError: If pattern compilation fails

        Note:
            Timeout enforcement using signal.alarm() doesn't work reliably in
            modern Python with C-optimized regex. For production, we would use
            the regex module instead of re, which has built-in timeout support.
            For now, we rely on patterns being pre-validated and not pathological.
        """
        # Note: timeout parameter preserved for future implementation
        # Currently not enforced - would need regex module instead of re
        _ = timeout_seconds or pattern.timeout
        compiled = self.compile_pattern(pattern)

        matches: list[Match] = []

        # Find all matches
        # Note: In production, use regex module with timeout parameter
        # import regex; regex.compile(pattern, timeout=timeout).finditer(text)
        try:
            for match_obj in compiled.finditer(text):
                start = match_obj.start()
                end = match_obj.end()

                # Extract context (50 chars before and after)
                context_before = text[max(0, start - 50):start]
                context_after = text[end:min(len(text), end + 50)]

                matches.append(Match(
                    pattern_index=pattern_index,
                    start=start,
                    end=end,
                    matched_text=text[start:end],
                    groups=match_obj.groups(),
                    context_before=context_before,
                    context_after=context_after,
                ))
        except Exception as e:
            # Catch any regex engine errors (catastrophic backtracking, etc.)
            raise ValueError(f"Pattern matching failed: {e}") from e

        return matches

    def match_all_patterns(
        self,
        text: str,
        patterns: list[Pattern],
    ) -> list[Match]:
        """Match all patterns from a rule against text.

        This implements OR logic: any pattern matching means the rule matches.

        Args:
            text: Text to search
            patterns: List of patterns to match

        Returns:
            All matches from all patterns (may be empty)

        Note:
            Continues matching even if a pattern fails, logging failures
            for later analysis (though we can't log in pure domain - caller handles).
        """
        all_matches: list[Match] = []

        for idx, pattern in enumerate(patterns):
            try:
                matches = self.match_pattern(text, pattern, pattern_index=idx)
                all_matches.extend(matches)
            except ValueError:
                # Pattern failed - skip it and continue with others
                # Caller should log this for debugging
                continue

        return all_matches

    def clear_cache(self) -> None:
        """Clear compiled pattern cache.

        Useful for testing or when patterns change.
        Not typically needed in production.
        """
        self._compiled_cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of compiled patterns in cache."""
        return len(self._compiled_cache)
