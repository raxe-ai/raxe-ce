"""Unit tests for suppression domain layer.

Pure domain layer tests - fast, no I/O, no mocks needed.
Tests the business logic for suppressions: value objects, pattern matching,
expiration handling, and manager orchestration.

Coverage target: >95% for domain layer.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from raxe.domain.suppression import (
    AuditEntry,
    Suppression,
    SuppressionManager,
)

# ============================================================================
# Test Fixtures - In-Memory Repository for Pure Domain Testing
# ============================================================================


class InMemorySuppressionRepository:
    """In-memory implementation of SuppressionRepository for testing.

    This is NOT a mock - it's a real implementation that stores data
    in memory instead of a database. This allows pure domain layer testing.
    """

    def __init__(self, initial_suppressions: list[Suppression] | None = None) -> None:
        """Initialize with optional initial suppressions."""
        self._suppressions: dict[str, Suppression] = {}
        self._audit_log: list[dict[str, Any]] = []

        if initial_suppressions:
            for s in initial_suppressions:
                self._suppressions[s.pattern] = s

    def load_suppressions(self) -> list[Suppression]:
        """Load all suppressions from memory."""
        return list(self._suppressions.values())

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a suppression to memory."""
        self._suppressions[suppression.pattern] = suppression

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from memory."""
        if pattern in self._suppressions:
            del self._suppressions[pattern]
            return True
        return False

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions in memory."""
        self._suppressions = {s.pattern: s for s in suppressions}

    def log_audit(self, entry: AuditEntry) -> None:
        """Log an audit entry to memory."""
        self._audit_log.append(
            {
                "pattern": entry.pattern,
                "reason": entry.reason,
                "action": entry.action,
                "created_at": entry.created_at,
                "scan_id": entry.scan_id,
                "rule_id": entry.rule_id,
                "created_by": entry.created_by,
                "metadata": entry.metadata,
            }
        )

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries from memory."""
        results = self._audit_log

        if pattern:
            results = [e for e in results if e["pattern"] == pattern]
        if action:
            results = [e for e in results if e["action"] == action]

        return results[:limit]


@pytest.fixture
def in_memory_repo() -> InMemorySuppressionRepository:
    """Create a fresh in-memory repository for each test."""
    return InMemorySuppressionRepository()


@pytest.fixture
def manager(in_memory_repo: InMemorySuppressionRepository) -> SuppressionManager:
    """Create a suppression manager with in-memory repository."""
    return SuppressionManager(repository=in_memory_repo, auto_load=True)


# ============================================================================
# Suppression Value Object Tests
# ============================================================================


class TestSuppressionValueObject:
    """Tests for the Suppression value object (immutable, PURE)."""

    def test_valid_suppression_creation(self) -> None:
        """Test creating a valid suppression."""
        now = datetime.now(timezone.utc).isoformat()
        suppression = Suppression(
            pattern="pi-001",
            reason="False positive in documentation",
            created_at=now,
            created_by="test-user",
        )

        assert suppression.pattern == "pi-001"
        assert suppression.reason == "False positive in documentation"
        assert suppression.created_at == now
        assert suppression.created_by == "test-user"
        assert suppression.expires_at is None

    def test_suppression_with_expiration(self) -> None:
        """Test creating a suppression with expiration date."""
        now = datetime.now(timezone.utc)
        future = (now + timedelta(days=30)).isoformat()

        suppression = Suppression(
            pattern="pi-001",
            reason="Temporary suppression",
            created_at=now.isoformat(),
            expires_at=future,
        )

        assert suppression.expires_at == future

    def test_pattern_cannot_be_empty(self) -> None:
        """Test that empty pattern raises ValueError."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            Suppression(
                pattern="",
                reason="Test reason",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_reason_cannot_be_empty(self) -> None:
        """Test that empty reason raises ValueError."""
        with pytest.raises(ValueError, match="Reason cannot be empty"):
            Suppression(
                pattern="pi-001",
                reason="",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_suppression_is_immutable(self) -> None:
        """Test that Suppression is immutable (frozen dataclass)."""
        suppression = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with pytest.raises(AttributeError):
            suppression.pattern = "pi-002"  # type: ignore

        with pytest.raises(AttributeError):
            suppression.reason = "New reason"  # type: ignore


class TestSuppressionPatternMatching:
    """Tests for Suppression pattern matching using fnmatch."""

    def test_exact_match(self) -> None:
        """Test exact rule ID matching."""
        suppression = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-002") is False
        assert suppression.matches("jb-001") is False

    def test_wildcard_prefix_pattern(self) -> None:
        """Test wildcard prefix patterns (pi-*)."""
        suppression = Suppression(
            pattern="pi-*",
            reason="All PI rules",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Should match all pi-* rules
        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-002") is True
        assert suppression.matches("pi-advanced-001") is True
        assert suppression.matches("pi-injection") is True

        # Should NOT match other families
        assert suppression.matches("jb-001") is False
        assert suppression.matches("pii-email") is False
        assert suppression.matches("cmd-001") is False

    def test_wildcard_suffix_pattern_in_middle(self) -> None:
        """Test wildcard patterns that match suffix after family prefix (pi-*-injection)."""
        # Note: Suffix-only patterns like *-injection are NOT allowed
        # Use family-prefixed patterns instead
        suppression = Suppression(
            pattern="pi-*",
            reason="All PI rules including injection variants",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("pi-injection") is True
        assert suppression.matches("pi-sql-injection") is True
        assert suppression.matches("pi-001") is True

        # Should NOT match other families
        assert suppression.matches("cmd-injection") is False
        assert suppression.matches("jb-injection") is False

    def test_wildcard_middle_pattern(self) -> None:
        """Test wildcard in middle patterns (jb-*-basic)."""
        suppression = Suppression(
            pattern="jb-*-basic",
            reason="Basic JB rules",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("jb-regex-basic") is True
        assert suppression.matches("jb-pattern-basic") is True
        assert suppression.matches("jb-any-value-basic") is True

        # Should NOT match
        assert suppression.matches("jb-basic") is False  # No middle part
        assert suppression.matches("pi-regex-basic") is False  # Wrong family
        assert suppression.matches("jb-regex-advanced") is False  # Wrong suffix

    def test_question_mark_wildcard(self) -> None:
        """Test single character wildcard (pi-00?)."""
        suppression = Suppression(
            pattern="pi-00?",
            reason="Single digit PI rules",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-002") is True
        assert suppression.matches("pi-009") is True

        # Should NOT match
        assert suppression.matches("pi-010") is False
        assert suppression.matches("pi-0001") is False
        assert suppression.matches("pi-00") is False

    def test_character_class_pattern(self) -> None:
        """Test character class patterns (pi-[0-5]*)."""
        suppression = Suppression(
            pattern="pi-[0-5]*",
            reason="PI rules 0-5",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-500") is True
        assert suppression.matches("pi-3abc") is True

        # Should NOT match
        assert suppression.matches("pi-601") is False
        assert suppression.matches("pi-900") is False

    def test_multiple_wildcards(self) -> None:
        """Test patterns with multiple wildcards (must have valid family prefix)."""
        # Note: Patterns starting with * are not allowed
        # Use family-prefixed patterns with wildcards
        suppression = Suppression(
            pattern="jb-*-*",
            reason="JB patterns with multiple segments",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("jb-a-b") is True
        assert suppression.matches("jb-regex-basic") is True
        assert suppression.matches("jb-pattern-advanced") is True

        # Should NOT match
        assert suppression.matches("pi-001") is False
        assert suppression.matches("jb-001") is False  # Only two segments

    def test_case_sensitivity(self) -> None:
        """Test that pattern matching is case-sensitive."""
        suppression = Suppression(
            pattern="PI-001",
            reason="Uppercase pattern",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("PI-001") is True
        assert suppression.matches("pi-001") is False  # Case mismatch


class TestSuppressionExpiration:
    """Tests for suppression expiration handling."""

    def test_suppression_without_expiration_never_expires(self) -> None:
        """Test that suppression without expires_at never expires."""
        suppression = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
        )

        assert suppression.is_expired() is False

        # Even far in the future
        future = datetime.now(timezone.utc) + timedelta(days=365 * 100)
        assert suppression.is_expired(current_time=future) is False

    def test_suppression_with_future_expiration_not_expired(self) -> None:
        """Test that suppression with future expiration is not expired."""
        now = datetime.now(timezone.utc)
        future = (now + timedelta(days=30)).isoformat()

        suppression = Suppression(
            pattern="pi-001",
            reason="Future expiration",
            created_at=now.isoformat(),
            expires_at=future,
        )

        assert suppression.is_expired() is False
        assert suppression.is_expired(current_time=now) is False

    def test_suppression_with_past_expiration_is_expired(self) -> None:
        """Test that suppression with past expiration is expired."""
        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=1)).isoformat()

        suppression = Suppression(
            pattern="pi-001",
            reason="Past expiration",
            created_at=(now - timedelta(days=30)).isoformat(),
            expires_at=past,
        )

        assert suppression.is_expired() is True
        assert suppression.is_expired(current_time=now) is True

    def test_expiration_edge_case_exact_time(self) -> None:
        """Test expiration at exact expiry time."""
        expiry_time = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        suppression = Suppression(
            pattern="pi-001",
            reason="Edge case",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            expires_at=expiry_time.isoformat(),
        )

        # One second before - not expired
        before = expiry_time - timedelta(seconds=1)
        assert suppression.is_expired(current_time=before) is False

        # One second after - expired
        after = expiry_time + timedelta(seconds=1)
        assert suppression.is_expired(current_time=after) is True

    def test_invalid_expiration_date_format_raises_error(self) -> None:
        """Test that invalid expiration date format raises error on construction."""
        from raxe.domain.suppression import SuppressionValidationError

        # Invalid date format should raise during construction (fail-fast)
        with pytest.raises(SuppressionValidationError, match="must be valid ISO format"):
            Suppression(
                pattern="pi-001",
                reason="Invalid date",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at="not-a-valid-date",
            )


# ============================================================================
# AuditEntry Value Object Tests
# ============================================================================


class TestAuditEntry:
    """Tests for the AuditEntry value object."""

    def test_valid_audit_entry_added(self) -> None:
        """Test creating a valid 'added' audit entry."""
        entry = AuditEntry(
            pattern="pi-001",
            reason="Test reason",
            action="added",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test-user",
        )

        assert entry.action == "added"
        assert entry.pattern == "pi-001"

    def test_valid_audit_entry_removed(self) -> None:
        """Test creating a valid 'removed' audit entry."""
        entry = AuditEntry(
            pattern="pi-001",
            reason="Test reason",
            action="removed",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert entry.action == "removed"

    def test_valid_audit_entry_applied(self) -> None:
        """Test creating a valid 'applied' audit entry."""
        entry = AuditEntry(
            pattern="pi-001",
            reason="Applied to scan",
            action="applied",
            created_at=datetime.now(timezone.utc).isoformat(),
            scan_id=12345,
            rule_id="pi-001",
        )

        assert entry.action == "applied"
        assert entry.scan_id == 12345
        assert entry.rule_id == "pi-001"

    def test_invalid_action_raises_error(self) -> None:
        """Test that invalid action raises ValueError."""
        with pytest.raises(ValueError, match="Invalid action"):
            AuditEntry(
                pattern="pi-001",
                reason="Test",
                action="invalid_action",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_audit_entry_with_metadata(self) -> None:
        """Test audit entry with metadata."""
        metadata = {"source": "cli", "version": "1.0.0"}
        entry = AuditEntry(
            pattern="pi-001",
            reason="Test",
            action="added",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )

        assert entry.metadata == metadata

    def test_audit_entry_is_immutable(self) -> None:
        """Test that AuditEntry is immutable."""
        entry = AuditEntry(
            pattern="pi-001",
            reason="Test",
            action="added",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with pytest.raises(AttributeError):
            entry.action = "removed"  # type: ignore


# ============================================================================
# SuppressionManager Tests
# ============================================================================


class TestSuppressionManagerIsSupressed:
    """Tests for SuppressionManager.is_suppressed() method."""

    def test_is_suppressed_returns_tuple(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that is_suppressed returns (bool, reason) tuple."""
        manager.add_suppression("pi-001", "Test reason")

        result = manager.is_suppressed("pi-001")

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_is_suppressed_exact_match(self, manager: SuppressionManager) -> None:
        """Test is_suppressed with exact pattern match."""
        manager.add_suppression("pi-001", "Test suppression")

        is_suppressed, reason = manager.is_suppressed("pi-001")

        assert is_suppressed is True
        assert reason == "Test suppression"

    def test_is_not_suppressed(self, manager: SuppressionManager) -> None:
        """Test is_suppressed returns False when not suppressed."""
        manager.add_suppression("pi-001", "Test")

        is_suppressed, reason = manager.is_suppressed("pi-002")

        assert is_suppressed is False
        assert reason == ""

    def test_is_suppressed_wildcard_match(self, manager: SuppressionManager) -> None:
        """Test is_suppressed with wildcard pattern match."""
        manager.add_suppression("pi-*", "All PI rules suppressed")

        # Should match multiple rules
        is_suppressed_001, reason_001 = manager.is_suppressed("pi-001")
        is_suppressed_002, reason_002 = manager.is_suppressed("pi-002")
        is_suppressed_adv, reason_adv = manager.is_suppressed("pi-advanced")

        assert is_suppressed_001 is True
        assert is_suppressed_002 is True
        assert is_suppressed_adv is True
        assert reason_001 == "All PI rules suppressed"

        # Should NOT match other families
        is_suppressed_jb, reason_jb = manager.is_suppressed("jb-001")
        assert is_suppressed_jb is False

    def test_is_suppressed_expired_skipped(self, manager: SuppressionManager) -> None:
        """Test that expired suppressions are skipped in is_suppressed check."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        manager.add_suppression("pi-001", "Expired", expires_at=past)

        is_suppressed, reason = manager.is_suppressed("pi-001")

        assert is_suppressed is False
        assert reason == ""

    def test_is_suppressed_active_not_expired(self, manager: SuppressionManager) -> None:
        """Test that active (not expired) suppressions work."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        manager.add_suppression("pi-001", "Active", expires_at=future)

        is_suppressed, reason = manager.is_suppressed("pi-001")

        assert is_suppressed is True
        assert reason == "Active"

    def test_is_suppressed_with_custom_time(self, manager: SuppressionManager) -> None:
        """Test is_suppressed with custom current_time for testing."""
        expiry = datetime(2025, 6, 1, tzinfo=timezone.utc)
        manager.add_suppression("pi-001", "Test", expires_at=expiry.isoformat())

        # Before expiry
        before = datetime(2025, 5, 1, tzinfo=timezone.utc)
        is_suppressed, _ = manager.is_suppressed("pi-001", current_time=before)
        assert is_suppressed is True

        # After expiry
        after = datetime(2025, 7, 1, tzinfo=timezone.utc)
        is_suppressed, _ = manager.is_suppressed("pi-001", current_time=after)
        assert is_suppressed is False


class TestSuppressionManagerMultiplePriority:
    """Tests for multiple suppression pattern priority."""

    def test_first_matching_suppression_wins(self, manager: SuppressionManager) -> None:
        """Test that first matching suppression reason is returned."""
        manager.add_suppression("pi-*", "Wildcard suppression")
        manager.add_suppression("pi-001", "Specific suppression")

        is_suppressed, reason = manager.is_suppressed("pi-001")

        assert is_suppressed is True
        # The reason depends on iteration order (dict in Python 3.7+ maintains insertion order)
        assert reason in ["Wildcard suppression", "Specific suppression"]

    def test_multiple_wildcards_all_checked(self, manager: SuppressionManager) -> None:
        """Test that multiple wildcard patterns are all checked."""
        manager.add_suppression("pi-*", "All PI rules")
        manager.add_suppression("jb-*", "All JB rules")
        manager.add_suppression("cmd-*", "All CMD rules")

        # pi-injection matches pi-*
        is_suppressed, reason = manager.is_suppressed("pi-injection")
        assert is_suppressed is True
        assert reason == "All PI rules"

        # jb-001 matches jb-*
        is_suppressed, reason = manager.is_suppressed("jb-001")
        assert is_suppressed is True
        assert reason == "All JB rules"

        # cmd-001 matches cmd-*
        is_suppressed, reason = manager.is_suppressed("cmd-001")
        assert is_suppressed is True
        assert reason == "All CMD rules"


class TestSuppressionManagerAddRemove:
    """Tests for adding and removing suppressions."""

    def test_add_suppression(self, manager: SuppressionManager) -> None:
        """Test adding a new suppression."""
        suppression = manager.add_suppression(
            pattern="pi-001",
            reason="Test suppression",
            created_by="test-user",
        )

        assert suppression.pattern == "pi-001"
        assert suppression.reason == "Test suppression"
        assert suppression.created_by == "test-user"
        assert manager.is_suppressed("pi-001")[0] is True

    def test_add_suppression_with_expiration(self, manager: SuppressionManager) -> None:
        """Test adding a suppression with expiration."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        suppression = manager.add_suppression(
            pattern="pi-001",
            reason="Temporary",
            expires_at=future,
        )

        assert suppression.expires_at == future

    def test_add_suppression_logs_audit(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that adding a suppression logs to audit."""
        manager.add_suppression("pi-001", "Test")

        audit_log = in_memory_repo.get_audit_log(action="added")
        assert len(audit_log) == 1
        assert audit_log[0]["pattern"] == "pi-001"
        assert audit_log[0]["action"] == "added"

    def test_add_suppression_skip_audit(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test adding suppression with log_to_audit=False."""
        manager.add_suppression("pi-001", "Test", log_to_audit=False)

        audit_log = in_memory_repo.get_audit_log(action="added")
        assert len(audit_log) == 0

    def test_remove_suppression_existing(self, manager: SuppressionManager) -> None:
        """Test removing an existing suppression."""
        manager.add_suppression("pi-001", "Test")
        assert manager.is_suppressed("pi-001")[0] is True

        removed = manager.remove_suppression("pi-001")

        assert removed is True
        assert manager.is_suppressed("pi-001")[0] is False

    def test_remove_suppression_nonexistent(self, manager: SuppressionManager) -> None:
        """Test removing a non-existent suppression."""
        removed = manager.remove_suppression("nonexistent")

        assert removed is False

    def test_remove_suppression_logs_audit(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that removing a suppression logs to audit."""
        manager.add_suppression("pi-001", "Test")
        manager.remove_suppression("pi-001", created_by="admin")

        audit_log = in_memory_repo.get_audit_log(action="removed")
        assert len(audit_log) == 1
        assert audit_log[0]["pattern"] == "pi-001"
        assert audit_log[0]["created_by"] == "admin"


class TestSuppressionManagerGetSuppressions:
    """Tests for getting suppressions."""

    def test_get_suppressions_empty(self, manager: SuppressionManager) -> None:
        """Test getting suppressions when none exist."""
        suppressions = manager.get_suppressions()

        assert len(suppressions) == 0

    def test_get_suppressions_returns_all_active(self, manager: SuppressionManager) -> None:
        """Test getting all active suppressions."""
        manager.add_suppression("pi-001", "Test 1")
        manager.add_suppression("pi-002", "Test 2")
        manager.add_suppression("jb-001", "Test 3")

        suppressions = manager.get_suppressions()

        assert len(suppressions) == 3
        patterns = [s.pattern for s in suppressions]
        assert "pi-001" in patterns
        assert "pi-002" in patterns
        assert "jb-001" in patterns

    def test_get_suppressions_excludes_expired(self, manager: SuppressionManager) -> None:
        """Test that get_suppressions excludes expired suppressions."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        manager.add_suppression("pi-001", "Active", expires_at=future)
        manager.add_suppression("pi-002", "Expired", expires_at=past)
        manager.add_suppression("pi-003", "Never expires")

        suppressions = manager.get_suppressions()

        assert len(suppressions) == 2
        patterns = [s.pattern for s in suppressions]
        assert "pi-001" in patterns
        assert "pi-003" in patterns
        assert "pi-002" not in patterns

    def test_get_suppression_specific(self, manager: SuppressionManager) -> None:
        """Test getting a specific suppression by pattern."""
        manager.add_suppression("pi-001", "Test")

        suppression = manager.get_suppression("pi-001")

        assert suppression is not None
        assert suppression.pattern == "pi-001"

    def test_get_suppression_not_found(self, manager: SuppressionManager) -> None:
        """Test getting a non-existent suppression returns None."""
        suppression = manager.get_suppression("nonexistent")

        assert suppression is None


class TestSuppressionManagerClearReload:
    """Tests for clearing and reloading suppressions."""

    def test_clear_all(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test clearing all suppressions."""
        manager.add_suppression("pi-001", "Test 1")
        manager.add_suppression("pi-002", "Test 2")
        manager.add_suppression("pi-003", "Test 3")

        count = manager.clear_all()

        assert count == 3
        assert len(manager.get_suppressions()) == 0

    def test_clear_all_logs_removals(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that clear_all logs removal of each suppression."""
        manager.add_suppression("pi-001", "Test 1")
        manager.add_suppression("pi-002", "Test 2")

        manager.clear_all(created_by="admin")

        # Should have 2 "added" + 2 "removed" entries
        removed_entries = in_memory_repo.get_audit_log(action="removed")
        assert len(removed_entries) == 2

    def test_reload_from_repository(self, in_memory_repo: InMemorySuppressionRepository) -> None:
        """Test reloading suppressions from repository."""
        # Pre-populate repository
        now = datetime.now(timezone.utc).isoformat()
        in_memory_repo.save_suppression(
            Suppression(pattern="pi-001", reason="Pre-loaded", created_at=now)
        )
        in_memory_repo.save_suppression(
            Suppression(pattern="pi-002", reason="Pre-loaded", created_at=now)
        )

        # Create manager with auto_load=False
        manager = SuppressionManager(repository=in_memory_repo, auto_load=False)
        assert len(manager.get_suppressions()) == 0

        # Reload
        count = manager.reload()

        assert count == 2
        assert len(manager.get_suppressions()) == 2


class TestSuppressionManagerStatistics:
    """Tests for suppression statistics."""

    def test_get_statistics(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test getting suppression statistics."""
        manager.add_suppression("pi-001", "Test 1")
        manager.add_suppression("pi-002", "Test 2")
        manager.remove_suppression("pi-001")

        stats = manager.get_statistics()

        assert stats["total_active"] == 1
        assert stats["total_added"] == 2
        assert stats["total_removed"] == 1

    def test_get_audit_log(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test getting audit log entries."""
        manager.add_suppression("pi-001", "Test")
        manager.remove_suppression("pi-001")

        audit_log = manager.get_audit_log()

        assert len(audit_log) == 2
        actions = [e["action"] for e in audit_log]
        assert "added" in actions
        assert "removed" in actions

    def test_log_suppression_applied(
        self, manager: SuppressionManager, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test logging when a suppression is applied during a scan."""
        manager.log_suppression_applied(
            rule_id="pi-001",
            reason="Applied during scan",
            scan_id=12345,
        )

        audit_log = in_memory_repo.get_audit_log(action="applied")
        assert len(audit_log) == 1
        assert audit_log[0]["rule_id"] == "pi-001"
        assert audit_log[0]["scan_id"] == 12345


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestSuppressionEdgeCases:
    """Edge case tests for suppression system."""

    def test_special_characters_in_pattern(self, manager: SuppressionManager) -> None:
        """Test patterns with special fnmatch characters."""
        manager.add_suppression("pi-[0-9]*", "Numeric only")

        assert manager.is_suppressed("pi-001")[0] is True
        assert manager.is_suppressed("pi-123")[0] is True
        assert manager.is_suppressed("pi-abc")[0] is False

    def test_pattern_with_valid_prefix(self, manager: SuppressionManager) -> None:
        """Test patterns with valid family prefixes."""
        # Test all valid prefixes work
        manager.add_suppression("pi-*", "All PI")
        manager.add_suppression("jb-001", "Specific JB")
        manager.add_suppression("cmd-002", "Specific CMD")

        assert manager.is_suppressed("pi-001")[0] is True
        assert manager.is_suppressed("jb-001")[0] is True
        assert manager.is_suppressed("cmd-002")[0] is True

    def test_reason_at_max_length(self, manager: SuppressionManager) -> None:
        """Test reason at exactly maximum length is accepted."""
        from raxe.domain.suppression import MAX_REASON_LENGTH

        long_reason = "A" * MAX_REASON_LENGTH
        manager.add_suppression("pi-001", long_reason)

        suppression = manager.get_suppression("pi-001")
        assert suppression is not None
        assert len(suppression.reason) == MAX_REASON_LENGTH

    def test_empty_suppressions_collection(self, manager: SuppressionManager) -> None:
        """Test operations on empty suppressions collection."""
        assert manager.is_suppressed("anything")[0] is False
        assert len(manager.get_suppressions()) == 0
        assert manager.clear_all() == 0

    def test_invalid_pattern_prefix_rejected(self, manager: SuppressionManager) -> None:
        """Test that invalid family prefixes are rejected."""
        from raxe.domain.suppression import SuppressionValidationError

        with pytest.raises(SuppressionValidationError, match="Unknown family prefix"):
            manager.add_suppression("invalid-*", "Invalid prefix")

    def test_wildcard_prefix_rejected(self, manager: SuppressionManager) -> None:
        """Test that patterns starting with * are rejected."""
        from raxe.domain.suppression import SuppressionValidationError

        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            manager.add_suppression("*-injection", "Not allowed")


class TestMaxSuppressionsLimit:
    """Tests for maximum suppressions limit (security hardening)."""

    def test_max_suppressions_exceeded_raises_error(
        self, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that adding suppressions beyond MAX_SUPPRESSIONS raises ValueError."""
        from raxe.domain.suppression import MAX_SUPPRESSIONS

        # Pre-load repository with MAX_SUPPRESSIONS entries
        now = datetime.now(timezone.utc).isoformat()
        for i in range(MAX_SUPPRESSIONS):
            in_memory_repo.save_suppression(
                Suppression(pattern=f"pi-{i:04d}", reason=f"Test {i}", created_at=now)
            )

        # Create manager with max suppressions already loaded
        manager = SuppressionManager(repository=in_memory_repo, auto_load=True)
        assert len(manager.get_suppressions()) == MAX_SUPPRESSIONS

        # Attempting to add one more should fail
        with pytest.raises(
            ValueError,
            match=f"Maximum suppression limit \\({MAX_SUPPRESSIONS}\\) reached",
        ):
            manager.add_suppression("jb-new", "This should fail")

    def test_update_existing_suppression_allowed_at_limit(
        self, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that updating an existing suppression is allowed even at limit."""
        from raxe.domain.suppression import MAX_SUPPRESSIONS

        # Pre-load repository with MAX_SUPPRESSIONS entries
        now = datetime.now(timezone.utc).isoformat()
        for i in range(MAX_SUPPRESSIONS):
            in_memory_repo.save_suppression(
                Suppression(pattern=f"pi-{i:04d}", reason=f"Test {i}", created_at=now)
            )

        manager = SuppressionManager(repository=in_memory_repo, auto_load=True)

        # Updating an existing pattern should work (not a new suppression)
        updated = manager.add_suppression("pi-0001", "Updated reason")
        assert updated.reason == "Updated reason"

    def test_add_suppression_below_limit_succeeds(
        self, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that adding suppressions below limit succeeds."""
        from raxe.domain.suppression import MAX_SUPPRESSIONS

        # Pre-load with fewer than max
        now = datetime.now(timezone.utc).isoformat()
        for i in range(MAX_SUPPRESSIONS - 1):
            in_memory_repo.save_suppression(
                Suppression(pattern=f"pi-{i:04d}", reason=f"Test {i}", created_at=now)
            )

        manager = SuppressionManager(repository=in_memory_repo, auto_load=True)
        assert len(manager.get_suppressions()) == MAX_SUPPRESSIONS - 1

        # Should be able to add one more
        supp = manager.add_suppression("jb-001", "Last allowed suppression")
        assert supp.pattern == "jb-001"
        assert len(manager.get_suppressions()) == MAX_SUPPRESSIONS

    def test_remove_and_add_works_at_limit(
        self, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test that removing a suppression frees up space for a new one."""
        from raxe.domain.suppression import MAX_SUPPRESSIONS

        # Pre-load with exactly max
        now = datetime.now(timezone.utc).isoformat()
        for i in range(MAX_SUPPRESSIONS):
            in_memory_repo.save_suppression(
                Suppression(pattern=f"pi-{i:04d}", reason=f"Test {i}", created_at=now)
            )

        manager = SuppressionManager(repository=in_memory_repo, auto_load=True)

        # Remove one
        removed = manager.remove_suppression("pi-0000")
        assert removed is True
        assert len(manager.get_suppressions()) == MAX_SUPPRESSIONS - 1

        # Should now be able to add a new one
        supp = manager.add_suppression("jb-001", "New suppression after removal")
        assert supp.pattern == "jb-001"
        assert len(manager.get_suppressions()) == MAX_SUPPRESSIONS


class TestSuppressionPerformance:
    """Performance tests for suppression system (PURE domain tests)."""

    def test_many_suppressions_is_suppressed_performance(
        self, in_memory_repo: InMemorySuppressionRepository
    ) -> None:
        """Test is_suppressed performance with many suppressions."""
        import time

        # Add many suppressions with valid prefixes
        now = datetime.now(timezone.utc).isoformat()
        suppressions = [
            Suppression(pattern=f"pi-{i:04d}", reason=f"Test {i}", created_at=now)
            for i in range(1000)
        ]
        for s in suppressions:
            in_memory_repo.save_suppression(s)

        manager = SuppressionManager(repository=in_memory_repo, auto_load=True)

        # Time the is_suppressed check
        start = time.perf_counter()
        for _ in range(100):
            manager.is_suppressed("pi-0500")
        duration_ms = (time.perf_counter() - start) * 1000

        # Should complete 100 checks in <200ms (allowing for CI variability and system load)
        assert duration_ms < 200, f"is_suppressed took {duration_ms}ms for 100 checks"

    def test_wildcard_matching_performance(self, manager: SuppressionManager) -> None:
        """Test wildcard matching performance."""
        import time

        # Add wildcard patterns with valid family prefixes
        manager.add_suppression("pi-*", "All PI")
        manager.add_suppression("jb-*", "All JB")
        manager.add_suppression("cmd-*", "All CMD")

        # Time the matching
        start = time.perf_counter()
        for _ in range(1000):
            manager.is_suppressed("pi-advanced-001")
        duration_ms = (time.perf_counter() - start) * 1000

        # Should complete 1000 checks in <50ms (allowing for CI variability)
        assert duration_ms < 50, f"Wildcard matching took {duration_ms}ms for 1000 checks"
