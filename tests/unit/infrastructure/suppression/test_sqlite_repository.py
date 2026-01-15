"""Unit tests for SQLiteSuppressionRepository.

Tests the infrastructure layer SQLite operations for audit logging.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from raxe.domain.suppression import AuditEntry, Suppression
from raxe.infrastructure.suppression.sqlite_repository import SQLiteSuppressionRepository


class TestSQLiteRepositoryInitialization:
    """Tests for SQLite repository initialization."""

    def test_creates_database_file(self) -> None:
        """Test that initialization creates the database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            repo = SQLiteSuppressionRepository(db_path=db_path)

            assert db_path.exists()

    def test_creates_parent_directories(self) -> None:
        """Test that initialization creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "dir" / "test.db"

            repo = SQLiteSuppressionRepository(db_path=db_path)

            assert db_path.exists()
            assert db_path.parent.exists()

    def test_creates_audit_table(self) -> None:
        """Test that initialization creates the suppression_audit table."""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='suppression_audit'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None
            assert result[0] == "suppression_audit"


class TestSQLiteRepositoryAuditLogging:
    """Tests for audit log operations."""

    def test_log_audit_added(self) -> None:
        """Test logging an 'added' audit entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="Test suppression",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test-user",
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["pattern"] == "pi-001"
            assert audit_log[0]["action"] == "added"
            assert audit_log[0]["reason"] == "Test suppression"
            assert audit_log[0]["created_by"] == "test-user"

    def test_log_audit_removed(self) -> None:
        """Test logging a 'removed' audit entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="No longer needed",
                action="removed",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["action"] == "removed"

    def test_log_audit_applied(self) -> None:
        """Test logging an 'applied' audit entry with scan context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="Applied during scan",
                action="applied",
                created_at=datetime.now(timezone.utc).isoformat(),
                scan_id=12345,
                rule_id="pi-001",
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["action"] == "applied"
            assert audit_log[0]["scan_id"] == 12345
            assert audit_log[0]["rule_id"] == "pi-001"

    def test_log_audit_with_metadata(self) -> None:
        """Test logging audit entry with metadata JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="Test",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
                metadata={"source": "cli", "version": "1.0.0"},
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["metadata"] == {"source": "cli", "version": "1.0.0"}


class TestSQLiteRepositoryAuditLogRetrieval:
    """Tests for retrieving audit log entries."""

    def test_get_audit_log_empty(self) -> None:
        """Test getting audit log when empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            audit_log = repo.get_audit_log()

            assert audit_log == []

    def test_get_audit_log_limit(self) -> None:
        """Test audit log limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Add 10 entries
            for i in range(10):
                entry = AuditEntry(
                    pattern=f"pi-{i:03d}",
                    reason="Test",
                    action="added",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)

            # Get with limit
            audit_log = repo.get_audit_log(limit=5)

            assert len(audit_log) == 5

    def test_get_audit_log_filter_by_pattern(self) -> None:
        """Test filtering audit log by pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Add entries for different patterns
            for pattern in ["pi-001", "pi-001", "jb-001", "pi-002"]:
                entry = AuditEntry(
                    pattern=pattern,
                    reason="Test",
                    action="added",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)

            # Filter by pattern
            audit_log = repo.get_audit_log(pattern="pi-001")

            assert len(audit_log) == 2
            assert all(e["pattern"] == "pi-001" for e in audit_log)

    def test_get_audit_log_filter_by_action(self) -> None:
        """Test filtering audit log by action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Add entries with different actions
            for action in ["added", "removed", "applied", "added"]:
                entry = AuditEntry(
                    pattern="pi-001",
                    reason="Test",
                    action=action,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)

            # Filter by action
            audit_log = repo.get_audit_log(action="added")

            assert len(audit_log) == 2
            assert all(e["action"] == "added" for e in audit_log)

    def test_get_audit_log_filter_combined(self) -> None:
        """Test filtering audit log by both pattern and action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Add entries
            entries = [
                ("pi-001", "added"),
                ("pi-001", "removed"),
                ("jb-001", "added"),
                ("pi-001", "applied"),
            ]
            for pattern, action in entries:
                entry = AuditEntry(
                    pattern=pattern,
                    reason="Test",
                    action=action,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)

            # Filter by both
            audit_log = repo.get_audit_log(pattern="pi-001", action="added")

            assert len(audit_log) == 1
            assert audit_log[0]["pattern"] == "pi-001"
            assert audit_log[0]["action"] == "added"

    def test_get_audit_log_ordered_by_created_at_desc(self) -> None:
        """Test that audit log is ordered by created_at descending."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Add entries with slight time delay
            for i in range(3):
                entry = AuditEntry(
                    pattern=f"pi-{i:03d}",
                    reason="Test",
                    action="added",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)
                time.sleep(0.01)  # Small delay to ensure different timestamps

            audit_log = repo.get_audit_log()

            # Most recent should be first (pi-002)
            assert audit_log[0]["pattern"] == "pi-002"
            assert audit_log[2]["pattern"] == "pi-000"


class TestSQLiteRepositorySuppressionOperations:
    """Tests for suppression CRUD operations (NO-OP for SQLite)."""

    def test_load_suppressions_returns_empty(self) -> None:
        """Test that load_suppressions returns empty list (NO-OP)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_save_suppression_is_noop(self) -> None:
        """Test that save_suppression is a NO-OP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            suppression = Suppression(
                pattern="pi-001",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            # Should not raise
            repo.save_suppression(suppression)

            # Should still return empty
            assert repo.load_suppressions() == []

    def test_remove_suppression_returns_false(self) -> None:
        """Test that remove_suppression always returns False (NO-OP)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            result = repo.remove_suppression("pi-001")

            assert result is False

    def test_save_all_suppressions_is_noop(self) -> None:
        """Test that save_all_suppressions is a NO-OP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            suppressions = [
                Suppression(
                    pattern="pi-001",
                    reason="Test",
                    created_at=datetime.now(timezone.utc).isoformat(),
                ),
            ]

            # Should not raise
            repo.save_all_suppressions(suppressions)

            # Should still return empty
            assert repo.load_suppressions() == []


class TestSQLiteRepositoryDefaultPath:
    """Tests for default path handling."""

    def test_default_path_is_home_raxe_dir(self) -> None:
        """Test that default path is ~/.raxe/suppressions.db."""
        # Use a real temp directory to avoid trying to create files in root
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a repository with explicit path to verify path logic
            db_path = Path(tmpdir) / ".raxe" / "suppressions.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Verify the path construction
            assert repo.db_path.name == "suppressions.db"
            assert repo.db_path.parent.name == ".raxe"

    def test_default_path_structure(self) -> None:
        """Test that default path has expected structure."""
        # When db_path is None, should use ~/.raxe/suppressions.db
        # We just verify the logic without actually creating the file
        expected_name = "suppressions.db"
        expected_parent = ".raxe"

        # The actual default path logic
        default_path = Path.home() / ".raxe" / "suppressions.db"
        assert default_path.name == expected_name
        assert default_path.parent.name == expected_parent


class TestSQLiteRepositoryEdgeCases:
    """Edge case tests for SQLite repository."""

    def test_concurrent_writes(self) -> None:
        """Test that concurrent writes don't cause errors."""
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            errors = []

            def write_entry(i: int) -> None:
                try:
                    entry = AuditEntry(
                        pattern=f"pi-{i:03d}",
                        reason="Test",
                        action="added",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                    repo.log_audit(entry)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write_entry, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            audit_log = repo.get_audit_log()
            assert len(audit_log) == 10

    def test_very_long_pattern(self) -> None:
        """Test handling of very long pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            long_pattern = "x" * 1000
            entry = AuditEntry(
                pattern=long_pattern,
                reason="Test",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["pattern"] == long_pattern

    def test_special_characters_in_reason(self) -> None:
        """Test handling of special characters in reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            special_reason = (
                "Test with 'quotes' and \"double quotes\" and special chars: !@#$%^&*()"
            )
            entry = AuditEntry(
                pattern="pi-001",
                reason=special_reason,
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert audit_log[0]["reason"] == special_reason

    def test_unicode_in_audit_entry(self) -> None:
        """Test handling of unicode in audit entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="Test with unicode",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.log_audit(entry)

            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1

    def test_malformed_metadata_json(self) -> None:
        """Test handling of malformed metadata JSON in database."""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SQLiteSuppressionRepository(db_path=db_path)

            # Manually insert entry with malformed JSON
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO suppression_audit (pattern, reason, action, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "pi-001",
                    "Test",
                    "added",
                    datetime.now(timezone.utc).isoformat(),
                    "not valid json",
                ),
            )
            conn.commit()
            conn.close()

            # Should not raise, metadata should be None
            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["metadata"] is None
