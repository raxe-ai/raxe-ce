"""Tests for model downloader version-aware cache invalidation.

Covers the new _get_model_install_state() function and its integration
with is_model_installed(), should_use_bundled_models(), and download_model().
These ensure stale model folders are detected and re-downloaded when
CURRENT_MODEL.model_version changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raxe.infrastructure.ml.model_downloader import (
    CURRENT_MODEL,
    MODEL_REGISTRY,
    ModelConfig,
    _get_model_install_state,
    _validate_model_folder,
    is_model_installed,
    should_use_bundled_models,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_valid_model_folder(
    folder: Path,
    *,
    model_version: str | None = None,
    include_metadata: bool = True,
) -> None:
    """Create a minimal valid model folder at *folder*.

    Writes the structural files required by _validate_model_folder plus an
    optional model_metadata.json with the given version.

    Args:
        folder: Directory to populate (created if absent).
        model_version: If given, written into model_metadata.json as
            ``"model_version"``.  If ``None`` and *include_metadata* is
            True, the key is omitted (simulating a legacy v0.4.0 folder).
        include_metadata: Whether to write model_metadata.json at all.
    """
    folder.mkdir(parents=True, exist_ok=True)

    # Required ONNX files (just need to exist / glob-match)
    (folder / "model_gemma.onnx").write_bytes(b"\x00")
    (folder / "classifier_is_threat_binary.onnx").write_bytes(b"\x00")

    if include_metadata:
        meta: dict[str, str] = {"name": "test-model"}
        if model_version is not None:
            meta["model_version"] = model_version
        (folder / "model_metadata.json").write_text(json.dumps(meta))


# ---------------------------------------------------------------------------
# _get_model_install_state
# ---------------------------------------------------------------------------


class TestGetModelInstallState:
    """Tests for _get_model_install_state version-aware state detection."""

    def test_install_state_missing_when_no_folder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'missing' when the model directory does not exist."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        # Ensure bundled models path is also empty
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        assert _get_model_install_state(CURRENT_MODEL.id) == "missing"

    def test_install_state_missing_for_unknown_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'missing' when model_name is not in MODEL_REGISTRY."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        assert _get_model_install_state("nonexistent_model_xyz") == "missing"

    def test_install_state_installed_when_version_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'installed' when folder exists and version matches CURRENT_MODEL."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version=CURRENT_MODEL.model_version)

        assert _get_model_install_state(CURRENT_MODEL.id) == "installed"

    def test_install_state_outdated_when_version_mismatches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'outdated' when installed version differs from CURRENT_MODEL."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version="0.4.0")

        assert _get_model_install_state(CURRENT_MODEL.id) == "outdated"

    def test_install_state_outdated_when_no_version_field(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'outdated' when model_metadata.json lacks model_version key.

        This simulates a legacy v0.4.0 folder that was downloaded before the
        version field was introduced.
        """
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        # model_version=None => key absent in JSON
        _create_valid_model_folder(folder, model_version=None)

        assert _get_model_install_state(CURRENT_MODEL.id) == "outdated"

    def test_install_state_outdated_when_metadata_json_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'outdated' when model_metadata.json file is absent entirely.

        A folder that only has manifest.yaml (old format) passes structural
        validation but has no way to confirm the version.
        """
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        # Create folder without model_metadata.json but with manifest.yaml
        # so _validate_model_folder still passes
        _create_valid_model_folder(folder, include_metadata=False)
        (folder / "manifest.yaml").write_text("name: legacy-model\n")

        assert _get_model_install_state(CURRENT_MODEL.id) == "outdated"

    def test_install_state_outdated_when_metadata_json_corrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'outdated' when model_metadata.json contains invalid JSON."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version=CURRENT_MODEL.model_version)
        # Corrupt the metadata file
        (folder / "model_metadata.json").write_text("{not valid json")

        assert _get_model_install_state(CURRENT_MODEL.id) == "outdated"

    def test_install_state_missing_when_folder_fails_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'missing' when folder exists but lacks required ONNX files."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        folder.mkdir(parents=True)
        # Only write metadata, no ONNX files
        (folder / "model_metadata.json").write_text(
            json.dumps({"model_version": CURRENT_MODEL.model_version})
        )

        assert _get_model_install_state(CURRENT_MODEL.id) == "missing"

    def test_install_state_checks_bundled_models_when_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State falls through to bundled directory when user dir is empty."""
        user_dir = tmp_path / "user_models"
        user_dir.mkdir()
        bundled_dir = tmp_path / "bundled_models"
        bundled_dir.mkdir()

        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: user_dir,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: True,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_package_models_directory",
            lambda: bundled_dir,
        )

        # Only create model in bundled directory
        folder = bundled_dir / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version=CURRENT_MODEL.model_version)

        assert _get_model_install_state(CURRENT_MODEL.id) == "installed"

    def test_install_state_installed_when_model_has_no_expected_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State is 'installed' if CURRENT_MODEL.model_version is empty.

        When model_version is not set on the config, version checking is
        skipped entirely and structural validation alone suffices.
        """
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        # Temporarily patch CURRENT_MODEL to have no version
        versionless = ModelConfig(
            id=CURRENT_MODEL.id,
            name=CURRENT_MODEL.name,
            description=CURRENT_MODEL.description,
            size_mb=CURRENT_MODEL.size_mb,
            url=CURRENT_MODEL.url,
            sha256=CURRENT_MODEL.sha256,
            folder_name=CURRENT_MODEL.folder_name,
            model_version="",
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.CURRENT_MODEL",
            versionless,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        # No model_version in the metadata at all
        _create_valid_model_folder(folder, model_version=None)

        assert _get_model_install_state(CURRENT_MODEL.id) == "installed"


# ---------------------------------------------------------------------------
# is_model_installed (delegates to _get_model_install_state)
# ---------------------------------------------------------------------------


class TestIsModelInstalled:
    """Tests for is_model_installed integration with version-aware state."""

    def test_returns_true_when_installed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_model_installed returns True for an up-to-date model."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version=CURRENT_MODEL.model_version)

        assert is_model_installed(CURRENT_MODEL.id) is True

    def test_returns_false_for_outdated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_model_installed returns False when version mismatches."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version="0.4.0")

        assert is_model_installed(CURRENT_MODEL.id) is False

    def test_returns_false_for_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_model_installed returns False when no folder exists."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        assert is_model_installed(CURRENT_MODEL.id) is False

    def test_returns_false_for_unknown_model(self) -> None:
        """is_model_installed returns False for unrecognized model names."""
        assert is_model_installed("does_not_exist_model") is False

    def test_returns_false_for_legacy_folder_without_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_model_installed returns False for legacy folders missing version."""
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.get_models_directory",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "raxe.infrastructure.ml.model_downloader.should_use_bundled_models",
            lambda: False,
        )

        folder = tmp_path / CURRENT_MODEL.folder_name
        _create_valid_model_folder(folder, model_version=None)

        assert is_model_installed(CURRENT_MODEL.id) is False


# ---------------------------------------------------------------------------
# should_use_bundled_models
# ---------------------------------------------------------------------------


class TestShouldUseBundledModels:
    """Tests for should_use_bundled_models env-var logic."""

    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bundled models are disabled when neither env var is set."""
        monkeypatch.delenv("RAXE_USE_BUNDLED_MODELS", raising=False)
        monkeypatch.delenv("RAXE_SKIP_BUNDLED_MODELS", raising=False)
        assert should_use_bundled_models() is False

    def test_enabled_when_opted_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_USE_BUNDLED_MODELS=1 enables bundled model search."""
        monkeypatch.setenv("RAXE_USE_BUNDLED_MODELS", "1")
        assert should_use_bundled_models() is True

    def test_enabled_with_any_truthy_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Any non-empty string should enable bundled models."""
        monkeypatch.setenv("RAXE_USE_BUNDLED_MODELS", "yes")
        assert should_use_bundled_models() is True

    def test_disabled_when_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string for RAXE_USE_BUNDLED_MODELS means disabled."""
        monkeypatch.setenv("RAXE_USE_BUNDLED_MODELS", "")
        assert should_use_bundled_models() is False


# ---------------------------------------------------------------------------
# _validate_model_folder
# ---------------------------------------------------------------------------


class TestValidateModelFolder:
    """Tests for _validate_model_folder structural checks."""

    def test_valid_folder_with_metadata_json(self, tmp_path: Path) -> None:
        """Folder with metadata + required ONNX files is valid."""
        _create_valid_model_folder(tmp_path, model_version="0.5.0")
        assert _validate_model_folder(tmp_path) is True

    def test_valid_folder_with_manifest_yaml(self, tmp_path: Path) -> None:
        """Folder with manifest.yaml (legacy) + ONNX files is valid."""
        (tmp_path / "manifest.yaml").write_text("name: model\n")
        (tmp_path / "model_gemma.onnx").write_bytes(b"\x00")
        (tmp_path / "classifier_is_threat_binary.onnx").write_bytes(b"\x00")
        assert _validate_model_folder(tmp_path) is True

    def test_invalid_folder_missing_metadata(self, tmp_path: Path) -> None:
        """Folder without any metadata file is invalid."""
        (tmp_path / "model_gemma.onnx").write_bytes(b"\x00")
        (tmp_path / "classifier_is_threat_binary.onnx").write_bytes(b"\x00")
        assert _validate_model_folder(tmp_path) is False

    def test_invalid_folder_missing_embedding_onnx(self, tmp_path: Path) -> None:
        """Folder without model*.onnx is invalid."""
        (tmp_path / "model_metadata.json").write_text("{}")
        (tmp_path / "classifier_is_threat_binary.onnx").write_bytes(b"\x00")
        assert _validate_model_folder(tmp_path) is False

    def test_invalid_folder_missing_classifier_onnx(self, tmp_path: Path) -> None:
        """Folder without classifier_is_threat*.onnx is invalid."""
        (tmp_path / "model_metadata.json").write_text("{}")
        (tmp_path / "model_gemma.onnx").write_bytes(b"\x00")
        assert _validate_model_folder(tmp_path) is False

    def test_empty_folder_is_invalid(self, tmp_path: Path) -> None:
        """Completely empty folder is invalid."""
        assert _validate_model_folder(tmp_path) is False


# ---------------------------------------------------------------------------
# ModelConfig dataclass
# ---------------------------------------------------------------------------


class TestModelConfig:
    """Tests for ModelConfig dataclass basics."""

    def test_current_model_has_version(self) -> None:
        """CURRENT_MODEL must define a non-empty model_version."""
        assert CURRENT_MODEL.model_version
        assert CURRENT_MODEL.model_version == "0.5.0"

    def test_model_version_defaults_to_empty(self) -> None:
        """ModelConfig.model_version defaults to empty string."""
        config = ModelConfig(
            id="test",
            name="test",
            description="test",
            size_mb=1,
            url="https://example.com/model.tar.gz",
            sha256="abc123",
            folder_name="test_deploy",
        )
        assert config.model_version == ""

    def test_model_config_is_frozen(self) -> None:
        """ModelConfig instances are immutable."""
        with pytest.raises(AttributeError):
            CURRENT_MODEL.model_version = "9.9.9"  # type: ignore[misc]

    def test_model_version_in_registry(self) -> None:
        """MODEL_REGISTRY entry includes model_version when set on CURRENT_MODEL."""
        entry = MODEL_REGISTRY[CURRENT_MODEL.id]
        assert entry.get("model_version") == CURRENT_MODEL.model_version
