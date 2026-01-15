"""Unit tests for suppression_factory.py.

Tests the factory functions and deprecation warnings for legacy .raxeignore files.
"""

import tempfile
import warnings
from pathlib import Path

from raxe.domain.suppression_factory import (
    _check_legacy_raxeignore,
    create_suppression_manager,
    create_suppression_manager_with_yaml,
)


class TestLegacyRaxeignoreWarning:
    """Tests for deprecation warning when .raxeignore is detected."""

    def test_warning_when_raxeignore_exists_without_yaml(self) -> None:
        """Test that deprecation warning is raised when .raxeignore exists without .raxe/suppressions.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create legacy .raxeignore file
            legacy_path = tmpdir_path / ".raxeignore"
            legacy_path.write_text("pi-001  # Legacy suppression")

            # YAML path that doesn't exist
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"

            # Check for deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_legacy_raxeignore(yaml_path=yaml_path)

                # Should have one deprecation warning
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "DEPRECATION WARNING" in str(w[0].message)
                assert ".raxeignore" in str(w[0].message)
                assert "UPDATE.md" in str(w[0].message)

    def test_no_warning_when_both_exist(self) -> None:
        """Test that no warning is raised when both .raxeignore and .raxe/suppressions.yaml exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create legacy .raxeignore file
            legacy_path = tmpdir_path / ".raxeignore"
            legacy_path.write_text("pi-001  # Legacy suppression")

            # Create new YAML config
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text("version: '1.0'\nsuppressions: []")

            # Check for no deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_legacy_raxeignore(yaml_path=yaml_path)

                # Should have no deprecation warnings
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) == 0

    def test_no_warning_when_neither_exist(self) -> None:
        """Test that no warning is raised when neither file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"

            # Check for no deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_legacy_raxeignore(yaml_path=yaml_path)

                # Should have no deprecation warnings
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) == 0

    def test_no_warning_when_only_yaml_exists(self) -> None:
        """Test that no warning is raised when only YAML config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create new YAML config (no .raxeignore)
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text("version: '1.0'\nsuppressions: []")

            # Check for no deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_legacy_raxeignore(yaml_path=yaml_path)

                # Should have no deprecation warnings
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) == 0


class TestCreateSuppressionManager:
    """Tests for create_suppression_manager factory function."""

    def test_creates_manager_with_defaults(self) -> None:
        """Test that factory creates manager with default settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            db_path = tmpdir_path / "test.db"

            # Suppress warnings for this test
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                manager = create_suppression_manager(
                    config_path=yaml_path,
                    db_path=db_path,
                    auto_load=False,
                )

            assert manager is not None
            assert len(manager.get_suppressions()) == 0

    def test_creates_manager_and_loads_yaml(self) -> None:
        """Test that factory creates manager and loads from YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            db_path = tmpdir_path / "test.db"

            # Create YAML config
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text("""version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Test suppression"
""")

            manager = create_suppression_manager(
                config_path=yaml_path,
                db_path=db_path,
                auto_load=True,
            )

            assert len(manager.get_suppressions()) == 1
            is_suppressed, reason = manager.is_suppressed("pi-001")
            assert is_suppressed is True
            assert reason == "Test suppression"

    def test_triggers_warning_for_legacy_file(self) -> None:
        """Test that factory triggers deprecation warning for legacy file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create legacy .raxeignore (no YAML)
            legacy_path = tmpdir_path / ".raxeignore"
            legacy_path.write_text("pi-001  # Legacy")

            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            db_path = tmpdir_path / "test.db"

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                manager = create_suppression_manager(
                    config_path=yaml_path,
                    db_path=db_path,
                    auto_load=False,
                )

                # Should have deprecation warning
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) == 1
                assert ".raxeignore" in str(deprecation_warnings[0].message)


class TestCreateSuppressionManagerWithYaml:
    """Tests for create_suppression_manager_with_yaml factory function."""

    def test_creates_manager_with_yaml_repository(self) -> None:
        """Test that factory creates manager with YamlCompositeRepository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            db_path = tmpdir_path / "test.db"

            # Create YAML config
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text("""version: "1.0"
suppressions:
  - pattern: "jb-001"
    reason: "YAML test"
""")

            manager = create_suppression_manager_with_yaml(
                yaml_path=yaml_path,
                db_path=db_path,
                auto_load=True,
            )

            assert len(manager.get_suppressions()) == 1
            is_suppressed, reason = manager.is_suppressed("jb-001")
            assert is_suppressed is True
            assert reason == "YAML test"

    def test_triggers_warning_for_legacy_file(self) -> None:
        """Test that yaml factory also triggers deprecation warning for legacy file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create legacy .raxeignore (no YAML)
            legacy_path = tmpdir_path / ".raxeignore"
            legacy_path.write_text("pi-001  # Legacy")

            yaml_path = tmpdir_path / ".raxe" / "suppressions.yaml"
            db_path = tmpdir_path / "test.db"

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                manager = create_suppression_manager_with_yaml(
                    yaml_path=yaml_path,
                    db_path=db_path,
                    auto_load=False,
                )

                # Should have deprecation warning
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) == 1
                assert ".raxeignore" in str(deprecation_warnings[0].message)
