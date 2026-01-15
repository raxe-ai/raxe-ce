"""Unit tests for YamlSuppressionRepository.

Tests the infrastructure layer file I/O operations for .raxe/suppressions.yaml files.
This tests YAML loading, parsing, validation, and saving functionality.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from raxe.domain.suppression import AuditEntry, Suppression, SuppressionAction
from raxe.infrastructure.suppression.yaml_repository import (
    DEFAULT_SUPPRESSIONS_PATH,
    SUPPORTED_SCHEMA_VERSION,
    YamlSuppressionRepository,
)


class TestYamlRepositoryLoading:
    """Tests for loading suppressions from .raxe/suppressions.yaml files."""

    def test_load_missing_file_returns_empty_list(self) -> None:
        """Test that missing file returns empty list (not error)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = YamlSuppressionRepository(
                config_path=Path(tmpdir) / ".raxe" / "suppressions.yaml"
            )

            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_load_empty_file_returns_empty_list(self) -> None:
        """Test that empty file returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_load_single_suppression(self) -> None:
        """Test loading a single suppression from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Known false positive"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"
            assert suppressions[0].reason == "Known false positive"
            assert suppressions[0].action == SuppressionAction.SUPPRESS

    def test_load_multiple_suppressions(self) -> None:
        """Test loading multiple suppressions from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "First suppression"
  - pattern: "jb-002"
    reason: "Second suppression"
  - pattern: "pi-*"
    reason: "Wildcard pattern"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 3
            patterns = [s.pattern for s in suppressions]
            assert "pi-001" in patterns
            assert "jb-002" in patterns
            assert "pi-*" in patterns

    def test_load_with_action_flag(self) -> None:
        """Test loading suppression with FLAG action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "jb-*"
    action: FLAG
    reason: "Under investigation"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].action == SuppressionAction.FLAG

    def test_load_with_action_log(self) -> None:
        """Test loading suppression with LOG action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "enc-003"
    action: LOG
    reason: "Monitoring false positive rate"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].action == SuppressionAction.LOG

    def test_load_action_case_insensitive(self) -> None:
        """Test that action parsing is case insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    action: flag
    reason: "Lower case action"
  - pattern: "pi-002"
    action: Flag
    reason: "Mixed case action"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 2
            assert suppressions[0].action == SuppressionAction.FLAG
            assert suppressions[1].action == SuppressionAction.FLAG

    def test_load_with_expiration_date(self) -> None:
        """Test loading suppression with expiration date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Temporary suppression"
    expires: "2025-06-01"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].expires_at is not None
            assert "2025-06-01" in suppressions[0].expires_at

    def test_load_with_full_iso_datetime(self) -> None:
        """Test loading suppression with full ISO datetime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Precise expiration"
    expires: "2025-06-01T15:30:00+00:00"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].expires_at is not None
            assert "2025-06-01" in suppressions[0].expires_at

    def test_load_sets_created_by_to_yaml_source(self) -> None:
        """Test that loaded suppressions have created_by set to yaml source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Test"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert suppressions[0].created_by == "yaml:suppressions.yaml"


class TestYamlRepositoryValidation:
    """Tests for validation during loading."""

    def test_skip_bare_wildcard_pattern(self) -> None:
        """Test that bare wildcard patterns are skipped with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "*"
    reason: "Bare wildcard should be skipped"
  - pattern: "pi-001"
    reason: "Valid pattern"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            # Only the valid pattern should be loaded
            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"

    def test_skip_missing_pattern(self) -> None:
        """Test that entries without pattern are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - reason: "No pattern"
  - pattern: "pi-001"
    reason: "Valid"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"

    def test_skip_missing_reason(self) -> None:
        """Test that entries without reason are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
  - pattern: "pi-002"
    reason: "Valid"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-002"

    def test_skip_invalid_action(self) -> None:
        """Test that entries with invalid action are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    action: INVALID_ACTION
    reason: "Invalid action"
  - pattern: "pi-002"
    reason: "Valid"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-002"

    def test_skip_invalid_expiration_date(self) -> None:
        """Test that entries with invalid expiration dates are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Invalid date"
    expires: "not-a-date"
  - pattern: "pi-002"
    reason: "Valid"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-002"

    def test_skip_non_dict_entries(self) -> None:
        """Test that non-dict entries in suppressions list are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - "just-a-string"
  - pattern: "pi-001"
    reason: "Valid"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-001"

    def test_skip_invalid_wildcard_pattern(self) -> None:
        """Test that wildcards without family prefix are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "*-injection"
    reason: "Suffix-only wildcard should be skipped"
  - pattern: "pi-*"
    reason: "Valid wildcard"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            # Only valid family-prefixed wildcard should load
            assert len(suppressions) == 1
            assert suppressions[0].pattern == "pi-*"


class TestYamlRepositoryErrorHandling:
    """Tests for error handling during loading."""

    def test_invalid_yaml_returns_empty_list(self) -> None:
        """Test that invalid YAML returns empty list with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001
    reason: "Missing quote
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_non_list_suppressions_returns_empty(self) -> None:
        """Test that non-list suppressions field returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions: "not-a-list"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_unsupported_version_logs_warning_but_continues(self) -> None:
        """Test that unsupported version logs warning but continues parsing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "2.0"
suppressions:
  - pattern: "pi-001"
    reason: "Test"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            # Should still parse successfully
            assert len(suppressions) == 1

    def test_missing_version_uses_default(self) -> None:
        """Test that missing version uses default and continues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
suppressions:
  - pattern: "pi-001"
    reason: "Test"
""")

            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1


class TestYamlRepositorySaving:
    """Tests for saving suppressions to .raxe/suppressions.yaml files."""

    def test_save_all_creates_file(self) -> None:
        """Test that save_all_suppressions creates the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="pi-001", reason="Test"),
            ]

            repo.save_all_suppressions(suppressions)

            assert config_path.exists()

    def test_save_all_creates_parent_directories(self) -> None:
        """Test that save_all_suppressions creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="pi-001", reason="Test"),
            ]

            repo.save_all_suppressions(suppressions)

            assert config_path.exists()
            assert config_path.parent.exists()

    def test_save_all_writes_valid_yaml(self) -> None:
        """Test that save_all_suppressions writes valid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="pi-001", reason="First"),
                Suppression(pattern="jb-002", reason="Second"),
            ]

            repo.save_all_suppressions(suppressions)

            # Load with a new repo to verify
            repo2 = YamlSuppressionRepository(config_path=config_path)
            loaded = repo2.load_suppressions()

            assert len(loaded) == 2
            patterns = [s.pattern for s in loaded]
            assert "pi-001" in patterns
            assert "jb-002" in patterns

    def test_save_all_includes_version(self) -> None:
        """Test that save_all_suppressions includes version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="pi-001", reason="Test"),
            ]

            repo.save_all_suppressions(suppressions)

            content = config_path.read_text()
            # YAML may use single or double quotes
            assert "version:" in content
            assert SUPPORTED_SCHEMA_VERSION in content

    def test_save_all_includes_action_only_for_non_default(self) -> None:
        """Test that action is only included if not SUPPRESS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="pi-001", reason="Default action"),
                Suppression(
                    pattern="pi-002",
                    reason="FLAG action",
                    action=SuppressionAction.FLAG,
                ),
            ]

            repo.save_all_suppressions(suppressions)

            content = config_path.read_text()
            # FLAG should appear (for pi-002)
            assert "action: FLAG" in content
            # SUPPRESS should NOT appear (it's the default)
            assert "action: SUPPRESS" not in content

    def test_save_all_includes_expiration(self) -> None:
        """Test that expiration dates are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(
                    pattern="pi-001",
                    reason="Expires",
                    expires_at="2025-06-01T23:59:59+00:00",
                ),
            ]

            repo.save_all_suppressions(suppressions)

            content = config_path.read_text()
            assert "expires:" in content
            assert "2025-06-01" in content

    def test_save_all_sorts_patterns(self) -> None:
        """Test that save_all_suppressions sorts patterns alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppressions = [
                Suppression(pattern="sec-pattern", reason="Z"),
                Suppression(pattern="cmd-pattern", reason="A"),
                Suppression(pattern="pi-pattern", reason="M"),
            ]

            repo.save_all_suppressions(suppressions)

            # Verify order by loading again
            repo2 = YamlSuppressionRepository(config_path=config_path)
            loaded = repo2.load_suppressions()

            # Should be sorted alphabetically
            assert loaded[0].pattern == "cmd-pattern"
            assert loaded[1].pattern == "pi-pattern"
            assert loaded[2].pattern == "sec-pattern"

    def test_save_all_includes_header_comments(self) -> None:
        """Test that save_all_suppressions includes header comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            repo.save_all_suppressions([])

            content = config_path.read_text()
            assert "RAXE Suppressions Configuration" in content
            assert "Format:" in content

    def test_save_all_empty_list(self) -> None:
        """Test that save_all_suppressions with empty list works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            repo.save_all_suppressions([])

            content = config_path.read_text()
            assert config_path.exists()
            assert "suppressions: []" in content


class TestYamlRepositoryInMemoryOperations:
    """Tests for in-memory operations before file save."""

    def test_save_suppression_adds_to_memory(self) -> None:
        """Test that save_suppression adds to in-memory cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppression = Suppression(pattern="pi-001", reason="Test")

            repo.save_suppression(suppression)

            assert "pi-001" in repo._suppressions

    def test_remove_suppression_removes_from_memory(self) -> None:
        """Test that remove_suppression removes from in-memory cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            suppression = Suppression(pattern="pi-001", reason="Test")
            repo.save_suppression(suppression)

            result = repo.remove_suppression("pi-001")

            assert result is True
            assert "pi-001" not in repo._suppressions

    def test_remove_suppression_nonexistent(self) -> None:
        """Test that removing non-existent suppression returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            result = repo.remove_suppression("nonexistent")

            assert result is False


class TestYamlRepositoryAuditLog:
    """Tests for audit log operations (NO-OP for YAML repository)."""

    def test_log_audit_is_noop(self) -> None:
        """Test that log_audit is a NO-OP (doesn't raise)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            entry = AuditEntry(
                pattern="pi-001",
                reason="Test",
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            # Should not raise
            repo.log_audit(entry)

    def test_get_audit_log_returns_empty(self) -> None:
        """Test that get_audit_log returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            result = repo.get_audit_log()

            assert result == []


class TestYamlRepositoryDefaultPath:
    """Tests for default path handling."""

    def test_default_path_is_cwd_raxe_suppressions_yaml(self) -> None:
        """Test that default path is .raxe/suppressions.yaml in cwd."""
        repo = YamlSuppressionRepository(config_path=None)

        assert repo.config_path.name == "suppressions.yaml"
        assert repo.config_path.parent.name == ".raxe"
        assert repo.config_path.parent.parent == Path.cwd()

    def test_default_path_matches_constant(self) -> None:
        """Test that default path matches DEFAULT_SUPPRESSIONS_PATH constant."""
        repo = YamlSuppressionRepository(config_path=None)

        expected = Path.cwd() / DEFAULT_SUPPRESSIONS_PATH
        assert repo.config_path == expected


class TestYamlRepositoryFileExists:
    """Tests for file_exists property."""

    def test_file_exists_false_when_missing(self) -> None:
        """Test file_exists returns False when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = YamlSuppressionRepository(
                config_path=Path(tmpdir) / ".raxe" / "suppressions.yaml"
            )

            assert repo.file_exists is False

    def test_file_exists_true_when_present(self) -> None:
        """Test file_exists returns True when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("version: '1.0'\nsuppressions: []")

            repo = YamlSuppressionRepository(config_path=config_path)

            assert repo.file_exists is True


class TestYamlRepositoryRoundTrip:
    """Tests for save-then-load round trip."""

    def test_round_trip_preserves_all_fields(self) -> None:
        """Test that save then load preserves all suppression fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            original = [
                Suppression(
                    pattern="pi-001",
                    reason="First",
                    action=SuppressionAction.SUPPRESS,
                    expires_at="2025-06-01T23:59:59+00:00",
                ),
                Suppression(
                    pattern="pi-*",
                    reason="Wildcard",
                    action=SuppressionAction.FLAG,
                ),
                Suppression(
                    pattern="jb-001",
                    reason="LOG action",
                    action=SuppressionAction.LOG,
                ),
            ]

            repo.save_all_suppressions(original)

            # Create new repo and load
            repo2 = YamlSuppressionRepository(config_path=config_path)
            loaded = repo2.load_suppressions()

            assert len(loaded) == 3

            # Verify pi-001
            pi001 = next(s for s in loaded if s.pattern == "pi-001")
            assert pi001.reason == "First"
            assert pi001.action == SuppressionAction.SUPPRESS
            assert pi001.expires_at is not None

            # Verify pi-* with FLAG action
            pi_wildcard = next(s for s in loaded if s.pattern == "pi-*")
            assert pi_wildcard.action == SuppressionAction.FLAG

            # Verify jb-001 with LOG action
            jb001 = next(s for s in loaded if s.pattern == "jb-001")
            assert jb001.action == SuppressionAction.LOG

    def test_round_trip_preserves_reasons_with_special_chars(self) -> None:
        """Test that save then load preserves reasons with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            repo = YamlSuppressionRepository(config_path=config_path)

            original = [
                Suppression(
                    pattern="pi-001",
                    reason="Reason with: colons, 'quotes', and \"double quotes\"",
                ),
            ]

            repo.save_all_suppressions(original)

            repo2 = YamlSuppressionRepository(config_path=config_path)
            loaded = repo2.load_suppressions()

            assert loaded[0].reason == "Reason with: colons, 'quotes', and \"double quotes\""


class TestYamlRepositoryEdgeCases:
    """Edge case tests for YAML repository."""

    def test_unicode_in_file(self) -> None:
        """Test handling of unicode in file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                """
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Unicode test"
""",
                encoding="utf-8",
            )

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1

    def test_very_long_reason(self) -> None:
        """Test that very long reasons are rejected (500 char limit)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            long_reason = "x" * 1000  # Exceeds 500 char limit
            config_path.write_text(f"""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "{long_reason}"
""")

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            # Long reasons are rejected (security limit: 500 chars)
            assert len(suppressions) == 0

    def test_reason_at_limit(self) -> None:
        """Test that reasons at exactly 500 chars work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            max_reason = "x" * 500  # Exactly at limit
            config_path.write_text(f"""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "{max_reason}"
""")

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            assert len(suppressions) == 1
            assert len(suppressions[0].reason) == 500

    def test_pattern_with_numbers(self) -> None:
        """Test patterns with various number formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Numeric pattern"
  - pattern: "pi-123456"
    reason: "Long number"
  - pattern: "pi-00*"
    reason: "Wildcard with numbers"
""")

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            assert len(suppressions) == 3
            patterns = [s.pattern for s in suppressions]
            assert "pi-001" in patterns
            assert "pi-123456" in patterns
            assert "pi-00*" in patterns

    def test_empty_suppressions_list(self) -> None:
        """Test empty suppressions list in YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
suppressions: []
""")

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            assert suppressions == []

    def test_missing_suppressions_key(self) -> None:
        """Test YAML file without suppressions key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
version: "1.0"
# No suppressions key
""")

            repo = YamlSuppressionRepository(config_path=config_path)
            suppressions = repo.load_suppressions()

            assert suppressions == []
