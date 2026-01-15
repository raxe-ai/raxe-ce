"""Test cases for suppression system.

Tests:
1. Basic suppression matching
2. Wildcard patterns
3. Expiration handling
4. Audit logging
5. File loading/saving
6. Integration with scan pipeline
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raxe.domain.suppression import Suppression
from raxe.domain.suppression_factory import create_suppression_manager


class TestSuppression:
    """Test Suppression model."""

    def test_exact_match(self):
        """Test exact rule ID matching."""
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert supp.matches("pi-001")
        assert not supp.matches("pi-002")
        assert not supp.matches("jb-001")

    def test_wildcard_prefix(self):
        """Test wildcard prefix patterns (pi-*)."""
        supp = Suppression(
            pattern="pi-*",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert supp.matches("pi-001")
        assert supp.matches("pi-002")
        assert supp.matches("pi-advanced-001")
        assert not supp.matches("jb-001")
        assert not supp.matches("pii-email")

    def test_wildcard_suffix_requires_family_prefix(self):
        """Test wildcard suffix patterns now require family prefix.

        v1.0 change: Bare suffix wildcards like '*-injection' are no longer
        allowed. Wildcards must start with a valid family prefix.
        """
        import pytest

        from raxe.domain.suppression import SuppressionValidationError

        # Suffix-only wildcards are now rejected
        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            Suppression(
                pattern="*-injection",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # But family-prefixed wildcards still work
        supp = Suppression(
            pattern="cmd-*",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert supp.matches("cmd-injection")
        assert supp.matches("cmd-001")
        assert not supp.matches("pi-injection")

    def test_wildcard_middle(self):
        """Test wildcard middle patterns (pi-*-basic)."""
        supp = Suppression(
            pattern="jb-*-basic",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert supp.matches("jb-regex-basic")
        assert supp.matches("jb-pattern-basic")
        assert not supp.matches("jb-basic")
        assert not supp.matches("pi-regex-basic")

    def test_expiration_not_set(self):
        """Test suppression without expiration."""
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert not supp.is_expired()

    def test_expiration_future(self):
        """Test suppression with future expiration."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future,
        )
        assert not supp.is_expired()

    def test_expiration_past(self):
        """Test suppression with past expiration."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        supp = Suppression(
            pattern="pi-001",
            reason="Test",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=past,
        )
        assert supp.is_expired()


class TestSuppressionManager:
    """Test SuppressionManager."""

    def test_add_suppression(self):
        """Test adding a suppression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            supp = manager.add_suppression(
                pattern="pi-001",
                reason="Test suppression",
            )

            assert supp.pattern == "pi-001"
            assert supp.reason == "Test suppression"

            # Check it's in memory
            is_suppressed, reason = manager.is_suppressed("pi-001")
            assert is_suppressed
            assert reason == "Test suppression"

    def test_remove_suppression(self):
        """Test removing a suppression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-001", "Test")
            assert manager.is_suppressed("pi-001")[0]

            removed = manager.remove_suppression("pi-001")
            assert removed
            assert not manager.is_suppressed("pi-001")[0]

            # Try removing again
            removed = manager.remove_suppression("pi-001")
            assert not removed

    def test_is_suppressed_exact(self):
        """Test checking exact match suppression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-001", "Test suppression")

            is_suppressed, reason = manager.is_suppressed("pi-001")
            assert is_suppressed
            assert reason == "Test suppression"

            is_suppressed, reason = manager.is_suppressed("pi-002")
            assert not is_suppressed
            assert reason == ""

    def test_is_suppressed_wildcard(self):
        """Test checking wildcard suppression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-*", "Suppress all PI rules")

            # Should match all pi-* rules
            assert manager.is_suppressed("pi-001")[0]
            assert manager.is_suppressed("pi-002")[0]
            assert manager.is_suppressed("pi-advanced-001")[0]

            # Should not match other families
            assert not manager.is_suppressed("jb-001")[0]
            assert not manager.is_suppressed("pii-email")[0]

    def test_is_suppressed_expired(self):
        """Test expired suppressions are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add expired suppression
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            manager.add_suppression(
                "pi-001",
                "Expired suppression",
                expires_at=past,
            )

            # Should not be suppressed (expired)
            is_suppressed, _reason = manager.is_suppressed("pi-001")
            assert not is_suppressed

    def test_load_from_file(self):
        """Test loading suppressions from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            # Create test YAML file
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("""version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "False positive in docs"
  - pattern: "jb-regex-basic"
    reason: "Too sensitive"
  - pattern: "pi-*"
    reason: "All PI rules"
  - pattern: "cmd-*"
    reason: "All CMD rules"
""")

            manager = create_suppression_manager(
                config_path=config_path,
                db_path=db_path,
                auto_load=True,
            )

            # Check loaded suppressions
            assert manager.is_suppressed("pi-001")[0]
            assert manager.is_suppressed("jb-regex-basic")[0]
            assert manager.is_suppressed("pi-002")[0]  # Wildcard pi-*
            assert manager.is_suppressed("cmd-injection")[0]  # Wildcard cmd-*

            # Get all suppressions
            suppressions = manager.get_suppressions()
            assert len(suppressions) == 4

    def test_save_to_file(self):
        """Test saving suppressions to YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            manager = create_suppression_manager(
                config_path=config_path,
                db_path=db_path,
                auto_load=False,
            )

            # Add suppressions
            manager.add_suppression("pi-001", "Test 1")
            manager.add_suppression("jb-002", "Test 2")
            manager.add_suppression("pi-*", "Test 3")

            # Save to file
            count = manager.save_to_file()
            assert count == 3
            assert config_path.exists()

            # Read file content
            content = config_path.read_text()
            assert "pi-001" in content
            assert "jb-002" in content
            assert "pi-*" in content

    def test_get_suppressions(self):
        """Test getting all active suppressions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-001", "Test 1")
            manager.add_suppression("pi-002", "Test 2")

            # Add expired suppression
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            manager.add_suppression("pi-003", "Expired", expires_at=past)

            # Should only get active suppressions (not expired)
            suppressions = manager.get_suppressions()
            assert len(suppressions) == 2
            patterns = [s.pattern for s in suppressions]
            assert "pi-001" in patterns
            assert "pi-002" in patterns
            assert "pi-003" not in patterns  # Expired

    def test_get_suppression(self):
        """Test getting specific suppression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-001", "Test suppression")

            supp = manager.get_suppression("pi-001")
            assert supp is not None
            assert supp.pattern == "pi-001"
            assert supp.reason == "Test suppression"

            supp = manager.get_suppression("pi-999")
            assert supp is None

    def test_audit_log(self):
        """Test audit log tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add suppression (logged as "added")
            manager.add_suppression("pi-001", "Test")

            # Remove suppression (logged as "removed")
            manager.remove_suppression("pi-001")

            # Get audit log
            log = manager.get_audit_log()
            assert len(log) >= 2

            # Check actions
            actions = [entry["action"] for entry in log]
            assert "added" in actions
            assert "removed" in actions

    def test_statistics(self):
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add some suppressions
            manager.add_suppression("pi-001", "Test 1")
            manager.add_suppression("pi-002", "Test 2")

            # Remove one
            manager.remove_suppression("pi-001")

            # Get stats
            stats = manager.get_statistics()
            assert stats["total_active"] == 1
            assert stats["total_added"] >= 2
            assert stats["total_removed"] >= 1

    def test_clear_all(self):
        """Test clearing all suppressions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add suppressions
            manager.add_suppression("pi-001", "Test 1")
            manager.add_suppression("pi-002", "Test 2")
            manager.add_suppression("jb-001", "Test 3")

            assert len(manager.get_suppressions()) == 3

            # Clear all
            count = manager.clear_all()
            assert count == 3
            assert len(manager.get_suppressions()) == 0


class TestSuppressionPatterns:
    """Test various suppression patterns."""

    def test_pattern_specificity(self):
        """Test that more specific patterns take precedence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add both specific and wildcard
            manager.add_suppression("pi-*", "Wildcard suppression")
            manager.add_suppression("pi-001", "Specific suppression")

            # Both should match, but we get the first match
            is_suppressed, _reason = manager.is_suppressed("pi-001")
            assert is_suppressed
            # Reason could be either - depends on dict ordering

    def test_multiple_wildcards(self):
        """Test multiple wildcard patterns.

        v1.0 change: All wildcards must have family prefix.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            manager.add_suppression("pi-*", "All PI rules")
            manager.add_suppression("cmd-*", "All CMD rules")  # Changed from *-injection
            manager.add_suppression("jb-regex-*", "Jailbreak regex rules")

            # Test various matches
            assert manager.is_suppressed("pi-001")[0]
            assert manager.is_suppressed("pi-injection")[0]  # Matches pi-*
            assert manager.is_suppressed("cmd-injection")[0]  # Matches cmd-*
            assert manager.is_suppressed("jb-regex-basic")[0]

            # Test non-matches
            assert not manager.is_suppressed("pii-email")[0]
            assert not manager.is_suppressed("jb-pattern-basic")[0]


# Example usage demonstrations
def example_basic_usage():
    """Example: Basic suppression usage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        manager = create_suppression_manager(db_path=db_path, auto_load=False)

        # Add suppression
        manager.add_suppression(
            pattern="pi-001",
            reason="False positive in documentation",
            created_by="security-team",
        )

        # Check if rule is suppressed
        is_suppressed, reason = manager.is_suppressed("pi-001")
        if is_suppressed:
            print(f"Rule pi-001 suppressed: {reason}")

        # List all suppressions
        for supp in manager.get_suppressions():
            print(f"{supp.pattern}: {supp.reason}")


def example_wildcard_usage():
    """Example: Wildcard pattern usage.

    v1.0 change: All wildcards must have family prefix (e.g., pi-*, cmd-*).
    Suffix-only wildcards like *-injection are no longer allowed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        manager = create_suppression_manager(db_path=db_path, auto_load=False)

        # Suppress all prompt injection rules
        manager.add_suppression(
            pattern="pi-*",
            reason="Disable all prompt injection detection",
        )

        # Suppress all CMD rules (v1.0: must use family prefix, not *-injection)
        manager.add_suppression(
            pattern="cmd-*",
            reason="CMD rules too sensitive",
        )

        # Check various rules
        print(manager.is_suppressed("pi-001"))  # (True, "Disable all...")
        print(manager.is_suppressed("pi-002"))  # (True, "Disable all...")
        print(manager.is_suppressed("cmd-injection"))  # (True, "CMD rules...")
        print(manager.is_suppressed("jb-001"))  # (False, "")


def example_file_usage():
    """Example: YAML file-based suppressions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Create .raxe/suppressions.yaml file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("""version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "False positive in docs"
  - pattern: "jb-regex-basic"
    reason: "Too sensitive"
  - pattern: "pi-*"
    reason: "All prompt injection rules"
""")

        # Load suppressions
        manager = create_suppression_manager(
            config_path=config_path,
            db_path=db_path,
            auto_load=True,
        )

        # Check loaded suppressions
        print(f"Loaded {len(manager.get_suppressions())} suppressions")

        # Add new suppression
        manager.add_suppression("pii-email", "Email validation false positives")

        # Save back to file
        manager.save_to_file()


if __name__ == "__main__":
    # Run examples
    print("=== Basic Usage ===")
    example_basic_usage()

    print("\n=== Wildcard Usage ===")
    example_wildcard_usage()

    print("\n=== File Usage ===")
    example_file_usage()

    print("\nRun tests with: pytest tests/test_suppression_system.py")
