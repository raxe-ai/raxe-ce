"""Unit tests for CompositeSuppressionRepository.

Tests the composite repository that combines YAML storage with SQLite audit logging.
"""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from raxe.domain.suppression import AuditEntry, Suppression
from raxe.infrastructure.suppression.composite_repository import (
    CompositeSuppressionRepository,
)


class TestCompositeRepositoryInitialization:
    """Tests for composite repository initialization."""

    def test_creates_both_repositories(self) -> None:
        """Test that composite creates both YAML and SQLite repositories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            assert repo.yaml_repo is not None
            assert repo.sqlite_repo is not None

    def test_creates_sqlite_database(self) -> None:
        """Test that SQLite database is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            assert db_path.exists()

    def test_exposes_paths(self) -> None:
        """Test that config_path and db_path are exposed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            assert repo.config_path == config_path
            assert repo.db_path == db_path

    def test_file_exists_property(self) -> None:
        """Test that file_exists property works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            # File should not exist initially
            assert repo.file_exists is False

            # Create the file
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("version: '1.0'\nsuppressions: []")

            assert repo.file_exists is True


class TestCompositeRepositoryLoadSave:
    """Tests for load/save operations (delegates to YAML repository)."""

    def test_load_suppressions_from_yaml(self) -> None:
        """Test that load_suppressions reads from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            # Create YAML file with suppressions
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("""version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Test suppression"
  - pattern: "jb-001"
    reason: "Another test"
""")

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 2
            patterns = [s.pattern for s in suppressions]
            assert "pi-001" in patterns
            assert "jb-001" in patterns

    def test_save_suppression_to_memory(self) -> None:
        """Test that save_suppression stores in YAML repository memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            suppression = Suppression(
                pattern="pi-001",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.save_suppression(suppression)

            # Verify it's in YAML repo memory
            assert "pi-001" in repo.yaml_repo._suppressions

    def test_save_all_writes_to_yaml(self) -> None:
        """Test that save_all_suppressions writes to YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            suppressions = [
                Suppression(
                    pattern="pi-001",
                    reason="Test",
                    created_at=datetime.now(timezone.utc).isoformat(),
                ),
            ]

            repo.save_all_suppressions(suppressions)

            assert config_path.exists()
            content = config_path.read_text()
            assert "pi-001" in content
            assert "version" in content

    def test_remove_suppression_from_memory(self) -> None:
        """Test that remove_suppression removes from YAML repository memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            suppression = Suppression(
                pattern="pi-001",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            repo.save_suppression(suppression)

            result = repo.remove_suppression("pi-001")

            assert result is True
            assert "pi-001" not in repo.yaml_repo._suppressions


class TestCompositeRepositoryAuditLog:
    """Tests for audit log operations (delegates to SQLite)."""

    def test_log_audit_to_sqlite(self) -> None:
        """Test that log_audit writes to SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            entry = AuditEntry(
                pattern="pi-001",
                reason="Test",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            repo.log_audit(entry)

            # Verify in SQLite
            audit_log = repo.get_audit_log()
            assert len(audit_log) == 1
            assert audit_log[0]["pattern"] == "pi-001"

    def test_get_audit_log_from_sqlite(self) -> None:
        """Test that get_audit_log reads from SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            # Add entries
            for action in ["added", "removed", "applied"]:
                entry = AuditEntry(
                    pattern="pi-001",
                    reason="Test",
                    action=action,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                repo.log_audit(entry)

            # Query with filters
            added_entries = repo.get_audit_log(action="added")
            assert len(added_entries) == 1

            all_entries = repo.get_audit_log()
            assert len(all_entries) == 3


class TestCompositeRepositoryIntegration:
    """Integration tests for composite repository."""

    def test_full_workflow(self) -> None:
        """Test full workflow: save, load, audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            # Save suppression
            now = datetime.now(timezone.utc).isoformat()
            suppression = Suppression(
                pattern="pi-001",
                reason="Test suppression",
                created_at=now,
            )
            repo.save_suppression(suppression)

            # Log audit
            entry = AuditEntry(
                pattern="pi-001",
                reason="Test suppression",
                action="added",
                created_at=now,
            )
            repo.log_audit(entry)

            # Persist to file
            repo.save_all_suppressions([suppression])

            # Create new repo and verify
            repo2 = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            # Suppressions should be loaded from file
            suppressions = repo2.load_suppressions()
            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"

            # Audit log should be in SQLite
            audit_log = repo2.get_audit_log()
            assert len(audit_log) == 1

    def test_yaml_and_audit_are_separate(self) -> None:
        """Test that YAML suppressions and audit log are separate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            repo = CompositeSuppressionRepository(
                config_path=config_path,
                db_path=db_path,
            )

            # Add suppression to file
            now = datetime.now(timezone.utc).isoformat()
            suppression = Suppression(
                pattern="pi-001",
                reason="YAML suppression",
                created_at=now,
            )
            repo.save_suppression(suppression)
            repo.save_all_suppressions([suppression])

            # Log audit entries for different patterns
            for i in range(5):
                entry = AuditEntry(
                    pattern=f"audit-{i:03d}",
                    reason="Audit entry",
                    action="applied",
                    created_at=now,
                )
                repo.log_audit(entry)

            # File should have 1 suppression
            suppressions = repo.load_suppressions()
            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"

            # Audit log should have 5 entries
            audit_log = repo.get_audit_log()
            assert len(audit_log) == 5
