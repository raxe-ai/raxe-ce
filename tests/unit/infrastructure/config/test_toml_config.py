"""Tests for TOML configuration management."""
from pathlib import Path

import pytest

from raxe.infrastructure.config.toml_config import (
    RaxeConfig,
    create_default_config,
)


class TestRaxeConfig:
    """Test complete configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RaxeConfig()

        assert config.core.environment == "production"
        assert config.detection.l1_enabled is True
        assert config.detection.l2_enabled is True
        assert config.telemetry.enabled is True
        assert config.performance.max_queue_size == 10000
        assert config.logging.level == "INFO"

    def test_save_and_load(self, tmp_path: Path):
        """Test saving and loading configuration."""
        config_file = tmp_path / "config.toml"

        # Create and save config
        config = RaxeConfig()
        config.core.api_key = "test-key"
        config.detection.mode = "thorough"
        config.save(config_file)

        # Load and verify
        loaded = RaxeConfig.from_file(config_file)

        assert loaded.core.api_key == "***"  # Should be redacted in save
        assert loaded.detection.mode == "thorough"

    def test_load_from_file(self, tmp_path: Path):
        """Test loading from TOML file."""
        config_file = tmp_path / "config.toml"

        # Write TOML manually
        config_file.write_text("""
[core]
api_key = "test-api-key"
environment = "development"

[detection]
l1_enabled = false
l2_enabled = true
mode = "fast"

[telemetry]
enabled = false
batch_size = 100
        """)

        # Load
        config = RaxeConfig.from_file(config_file)

        assert config.core.api_key == "test-api-key"
        assert config.core.environment == "development"
        assert config.detection.l1_enabled is False
        assert config.detection.mode == "fast"
        assert config.telemetry.enabled is False
        assert config.telemetry.batch_size == 100

    def test_load_missing_file(self, tmp_path: Path):
        """Test loading non-existent file."""
        config_file = tmp_path / "missing.toml"

        with pytest.raises(FileNotFoundError):
            RaxeConfig.from_file(config_file)

    def test_load_invalid_toml(self, tmp_path: Path):
        """Test loading invalid TOML."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("not valid toml [[[")

        with pytest.raises(ValueError):
            RaxeConfig.from_file(config_file)


class TestEnvironmentVariables:
    """Test environment variable configuration."""

    def test_load_from_env(self, monkeypatch):
        """Test loading from environment variables."""
        monkeypatch.setenv("RAXE_CORE_API_KEY", "env-api-key")
        monkeypatch.setenv("RAXE_DETECTION_MODE", "fast")
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "false")
        monkeypatch.setenv("RAXE_LOG_LEVEL", "DEBUG")

        config = RaxeConfig.from_env()

        assert config.core.api_key == "env-api-key"
        assert config.detection.mode == "fast"
        assert config.telemetry.enabled is False
        assert config.logging.level == "DEBUG"

    def test_env_bool_parsing(self, monkeypatch):
        """Test boolean environment variable parsing."""
        monkeypatch.setenv("RAXE_DETECTION_L1_ENABLED", "true")
        monkeypatch.setenv("RAXE_DETECTION_L2_ENABLED", "false")

        config = RaxeConfig.from_env()

        assert config.detection.l1_enabled is True
        assert config.detection.l2_enabled is False

    def test_env_int_parsing(self, monkeypatch):
        """Test integer environment variable parsing."""
        monkeypatch.setenv("RAXE_TELEMETRY_BATCH_SIZE", "100")
        monkeypatch.setenv("RAXE_PERFORMANCE_MAX_QUEUE_SIZE", "5000")

        config = RaxeConfig.from_env()

        assert config.telemetry.batch_size == 100
        assert config.performance.max_queue_size == 5000

    def test_env_float_parsing(self, monkeypatch):
        """Test float environment variable parsing."""
        monkeypatch.setenv("RAXE_DETECTION_CONFIDENCE_THRESHOLD", "0.8")

        config = RaxeConfig.from_env()

        assert config.detection.confidence_threshold == 0.8


class TestConfigFallbackChain:
    """Test configuration fallback priority."""

    def test_explicit_path_priority(self, tmp_path: Path):
        """Test that explicit path has highest priority."""
        explicit_config = tmp_path / "explicit.toml"
        explicit_config.write_text("""
[detection]
mode = "explicit"
        """)

        config = RaxeConfig.load(config_path=explicit_config)

        assert config.detection.mode == "explicit"

    def test_fallback_to_defaults(self):
        """Test fallback to defaults when no config found."""
        config = RaxeConfig.load(config_path=Path("/nonexistent/path.toml"))

        # Should use defaults (from env or defaults)
        assert config.detection.mode in ("fast", "balanced", "thorough")


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test that valid config passes validation."""
        config = RaxeConfig()

        errors = config.validate()

        assert errors == []

    def test_invalid_confidence_threshold(self):
        """Test validation of confidence threshold."""
        config = RaxeConfig()
        config.detection.confidence_threshold = 1.5  # Invalid (>1)

        errors = config.validate()

        assert len(errors) > 0
        assert "confidence_threshold" in errors[0]

    def test_invalid_queue_size(self):
        """Test validation of queue size."""
        config = RaxeConfig()
        config.performance.max_queue_size = 10  # Too small

        errors = config.validate()

        assert len(errors) > 0
        assert "max_queue_size" in errors[0]

    def test_invalid_batch_size(self):
        """Test validation of batch size."""
        config = RaxeConfig()
        config.telemetry.batch_size = 0  # Invalid

        errors = config.validate()

        assert len(errors) > 0
        assert "batch_size" in errors[0]


class TestConfigUpdate:
    """Test configuration updates."""

    def test_update_value(self):
        """Test updating config value by path."""
        config = RaxeConfig()

        config.update("detection.mode", "fast")

        assert config.detection.mode == "fast"

    def test_update_invalid_section(self):
        """Test updating invalid section."""
        config = RaxeConfig()

        with pytest.raises(ValueError, match="Invalid section"):
            config.update("invalid.key", "value")

    def test_update_invalid_key(self):
        """Test updating invalid key."""
        config = RaxeConfig()

        with pytest.raises(ValueError, match="Invalid key"):
            config.update("detection.invalid_key", "value")

    def test_get_value(self):
        """Test getting config value by path."""
        config = RaxeConfig()
        config.detection.mode = "thorough"

        value = config.get("detection.mode")

        assert value == "thorough"

    def test_get_invalid_path(self):
        """Test getting invalid path."""
        config = RaxeConfig()

        with pytest.raises(ValueError):
            config.get("invalid.path")


class TestConfigSerialization:
    """Test configuration serialization."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = RaxeConfig()
        config.core.api_key = "secret-key"

        data = config.to_dict()

        assert "core" in data
        assert "detection" in data
        assert data["core"]["api_key"] == "***"  # Redacted

    def test_roundtrip(self, tmp_path: Path):
        """Test save and load roundtrip."""
        config_file = tmp_path / "config.toml"

        # Create config
        config1 = RaxeConfig()
        config1.detection.mode = "fast"
        config1.telemetry.batch_size = 75

        # Save
        config1.save(config_file)

        # Load
        config2 = RaxeConfig.from_file(config_file)

        # Compare (excluding redacted fields)
        assert config2.detection.mode == config1.detection.mode
        assert config2.telemetry.batch_size == config1.telemetry.batch_size


class TestCreateDefaultConfig:
    """Test default config creation."""

    def test_create_default(self, tmp_path: Path):
        """Test creating default configuration file."""
        config_file = tmp_path / "config.toml"

        config = create_default_config(config_file)

        assert config_file.exists()
        assert config.core.environment == "production"

        # Should be loadable
        loaded = RaxeConfig.from_file(config_file)
        assert loaded.core.environment == "production"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
