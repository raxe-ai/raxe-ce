"""Tests for RAXE models CLI commands.

Tests cover:
- models list
- models list with filters
- models info
- models set-default
- models compare
- models download
- models status
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.models import models


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def _make_mock_model(
    model_id: str = "v1.0_onnx_int8",
    name: str = "Gemma Compact INT8",
    variant: str = "onnx_int8",
    status_value: str = "active",
    p95_latency: float = 8.5,
    binary_f1: float = 0.93,
    memory_mb: int = 64,
):
    """Create a mock model metadata object."""
    model = MagicMock()
    model.model_id = model_id
    model.name = name
    model.variant = variant
    model.version = "1.0.0"
    model.description = f"Test model {name}"
    model.runtime_type = "onnx"
    model.tags = ["fast", "production"]
    model.recommended_for = ["Low latency scanning"]
    model.not_recommended_for = ["Maximum accuracy"]
    model.file_path = f"/models/{model_id}"

    model.status = MagicMock()
    model.status.value = status_value
    model.is_active = status_value == "active"
    model.is_experimental = status_value == "experimental"

    model.performance = MagicMock()
    model.performance.p50_latency_ms = p95_latency * 0.7
    model.performance.p95_latency_ms = p95_latency
    model.performance.p99_latency_ms = p95_latency * 1.3
    model.performance.throughput_per_sec = 1000
    model.performance.memory_mb = memory_mb

    model.accuracy = MagicMock()
    model.accuracy.binary_f1 = binary_f1
    model.accuracy.family_f1 = binary_f1 - 0.05
    model.accuracy.subfamily_f1 = binary_f1 - 0.1
    model.accuracy.false_positive_rate = 0.02
    model.accuracy.false_negative_rate = 0.05

    model.requirements = MagicMock()
    model.requirements.requires_gpu = False
    model.requirements.min_runtime_version = "1.15.0"

    model.file_info = MagicMock()
    model.file_info.filename = f"{model_id}.onnx"
    model.file_info.size_mb = 64.0

    return model


class TestModelsList:
    """Tests for models list command."""

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_list(self, mock_get_registry, runner):
        """Test listing all models."""
        registry = mock_get_registry.return_value
        registry.list_models.return_value = [
            _make_mock_model("v1.0_bundle", "Bundle", "bundle"),
            _make_mock_model("v1.0_onnx_int8", "INT8", "onnx_int8"),
        ]

        result = runner.invoke(models, ["list"])

        assert result.exit_code == 0
        assert "v1.0_bundle" in result.output or "Bundle" in result.output

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_list_empty(self, mock_get_registry, runner):
        """Test listing models when none exist."""
        registry = mock_get_registry.return_value
        registry.list_models.return_value = []

        result = runner.invoke(models, ["list"])

        assert result.exit_code == 0
        assert "no models" in result.output.lower()

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_list_filter_status(self, mock_get_registry, runner):
        """Test listing models with status filter."""
        registry = mock_get_registry.return_value
        registry.list_models.return_value = [
            _make_mock_model("v1.0_onnx_int8", status_value="active"),
        ]

        result = runner.invoke(models, ["list", "--status", "active"])

        assert result.exit_code == 0
        registry.list_models.assert_called_once()

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_list_filter_runtime(self, mock_get_registry, runner):
        """Test listing models with runtime filter."""
        registry = mock_get_registry.return_value
        registry.list_models.return_value = [
            _make_mock_model("v1.0_onnx_int8", variant="onnx_int8"),
        ]

        result = runner.invoke(models, ["list", "--runtime", "onnx_int8"])

        assert result.exit_code == 0


class TestModelsInfo:
    """Tests for models info command."""

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_info_found(self, mock_get_registry, runner):
        """Test showing model info for existing model."""
        registry = mock_get_registry.return_value
        registry.get_model.return_value = _make_mock_model()

        result = runner.invoke(models, ["info", "v1.0_onnx_int8"])

        assert result.exit_code == 0
        assert "Gemma Compact INT8" in result.output or "v1.0_onnx_int8" in result.output

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_info_not_found(self, mock_get_registry, runner):
        """Test showing model info for non-existent model."""
        registry = mock_get_registry.return_value
        registry.get_model.return_value = None
        registry.list_models.return_value = [_make_mock_model()]

        result = runner.invoke(models, ["info", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestModelsSetDefault:
    """Tests for models set-default command."""

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_set_default(self, mock_get_registry, runner, tmp_path):
        """Test setting default model."""

        import yaml

        registry = mock_get_registry.return_value
        registry.get_model.return_value = _make_mock_model()

        # Create a temporary config
        config_file = tmp_path / ".raxe" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("version: 1.0.0\n")

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(models, ["set-default", "v1.0_onnx_int8"])

        assert result.exit_code == 0
        assert "v1.0_onnx_int8" in result.output

        # Verify config was updated
        with open(config_file) as f:
            config = yaml.safe_load(f)
        assert config["l2_model"]["model_id"] == "v1.0_onnx_int8"

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_set_default_not_found(self, mock_get_registry, runner):
        """Test setting default to non-existent model."""
        registry = mock_get_registry.return_value
        registry.get_model.return_value = None

        result = runner.invoke(models, ["set-default", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestModelsCompare:
    """Tests for models compare command."""

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_compare_specific(self, mock_get_registry, runner):
        """Test comparing specific models."""
        registry = mock_get_registry.return_value
        m1 = _make_mock_model("v1.0_bundle", "Bundle", "bundle", p95_latency=12.0)
        m2 = _make_mock_model("v1.0_onnx_int8", "INT8", "onnx_int8", p95_latency=8.0)
        model_map = {"v1.0_bundle": m1, "v1.0_onnx_int8": m2}
        registry.get_model.side_effect = lambda mid: model_map.get(mid)

        result = runner.invoke(models, ["compare", "v1.0_bundle", "v1.0_onnx_int8"])

        assert result.exit_code == 0
        assert "comparison" in result.output.lower() or "fastest" in result.output.lower()

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_compare_all(self, mock_get_registry, runner):
        """Test comparing all active models (no args)."""
        registry = mock_get_registry.return_value
        m1 = _make_mock_model("v1.0_bundle", "Bundle", "bundle")
        m2 = _make_mock_model("v1.0_onnx_int8", "INT8", "onnx_int8")
        registry.compare_models.return_value = {"v1.0_bundle": m1, "v1.0_onnx_int8": m2}

        result = runner.invoke(models, ["compare"])

        assert result.exit_code == 0

    @patch("raxe.domain.ml.model_registry.get_registry")
    def test_models_compare_empty(self, mock_get_registry, runner):
        """Test comparing when no models found."""
        registry = mock_get_registry.return_value
        registry.compare_models.return_value = {}

        result = runner.invoke(models, ["compare"])

        assert result.exit_code == 0
        assert "no models" in result.output.lower()


class TestModelsDownload:
    """Tests for models download command."""

    @patch("raxe.infrastructure.ml.model_downloader.get_available_models")
    @patch("raxe.infrastructure.ml.model_downloader.is_model_installed")
    @patch("raxe.infrastructure.ml.model_downloader.get_remote_file_size")
    @patch("raxe.infrastructure.ml.model_downloader.download_model")
    @patch(
        "raxe.infrastructure.ml.model_downloader.MODEL_REGISTRY",
        {
            "gemma-compact": {
                "name": "Gemma Compact",
                "url": "https://example.com/model.onnx",
                "size_mb": 329,
            },
        },
    )
    @patch("raxe.infrastructure.ml.model_downloader.DEFAULT_MODEL", "gemma-compact")
    def test_models_download_default(
        self,
        mock_download,
        mock_remote_size,
        mock_installed,
        mock_available,
        runner,
    ):
        """Test downloading default model."""
        mock_available.return_value = [
            {
                "id": "gemma-compact",
                "installed": False,
                "is_default": True,
                "description": "Default model",
                "size_mb": 329,
            },
        ]
        mock_installed.return_value = False
        mock_remote_size.return_value = 329 * 1024 * 1024
        mock_download.return_value = "/models/gemma-compact"

        result = runner.invoke(models, ["download"])

        assert result.exit_code == 0
        mock_download.assert_called_once()

    @patch("raxe.infrastructure.ml.model_downloader.get_available_models")
    @patch("raxe.infrastructure.ml.model_downloader.is_model_installed")
    @patch(
        "raxe.infrastructure.ml.model_downloader.MODEL_REGISTRY",
        {
            "gemma-compact": {
                "name": "Gemma Compact",
                "url": "https://example.com/model.onnx",
                "size_mb": 329,
            },
        },
    )
    @patch("raxe.infrastructure.ml.model_downloader.DEFAULT_MODEL", "gemma-compact")
    def test_models_download_already_installed(
        self,
        mock_installed,
        mock_available,
        runner,
    ):
        """Test downloading model that already exists."""
        mock_available.return_value = [
            {
                "id": "gemma-compact",
                "installed": True,
                "is_default": True,
                "description": "Default model",
                "size_mb": 329,
            },
        ]
        mock_installed.return_value = True

        result = runner.invoke(models, ["download"])

        assert result.exit_code == 0
        assert "already installed" in result.output.lower()


class TestModelsStatus:
    """Tests for models status command."""

    @patch("raxe.infrastructure.ml.model_downloader.get_package_models_directory")
    @patch("raxe.infrastructure.ml.model_downloader.get_models_directory")
    @patch("raxe.infrastructure.ml.model_downloader.get_available_models")
    def test_models_status(self, mock_available, mock_dir, mock_pkg_dir, runner):
        """Test models status command."""
        mock_available.return_value = [
            {"id": "gemma-compact", "installed": True, "is_default": True, "size_mb": 329},
        ]
        mock_dir.return_value = "/home/user/.raxe/models"
        mock_pkg_dir.return_value = "/site-packages/raxe/models"

        result = runner.invoke(models, ["status"])

        assert result.exit_code == 0
        assert "1" in result.output  # 1/1 installed

    @patch("raxe.infrastructure.ml.model_downloader.get_package_models_directory")
    @patch("raxe.infrastructure.ml.model_downloader.get_models_directory")
    @patch("raxe.infrastructure.ml.model_downloader.get_available_models")
    def test_models_status_none_installed(self, mock_available, mock_dir, mock_pkg_dir, runner):
        """Test models status when no models installed."""
        mock_available.return_value = [
            {"id": "gemma-compact", "installed": False, "is_default": True, "size_mb": 329},
        ]
        mock_dir.return_value = "/home/user/.raxe/models"
        mock_pkg_dir.return_value = "/site-packages/raxe/models"

        result = runner.invoke(models, ["status"])

        assert result.exit_code == 0
        assert "0" in result.output  # 0/1 installed
        assert "no ml models" in result.output.lower() or "not installed" in result.output.lower()
