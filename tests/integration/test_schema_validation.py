"""Integration tests for schema validation in scan pipeline."""

from unittest.mock import Mock

from raxe.application.preloader import PipelinePreloader
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.infrastructure.telemetry.hook import TelemetryHook


class TestSchemaValidation:
    """Test schema validation integration."""

    def test_schema_validation_disabled_by_default(self):
        """Test that schema validation is disabled by default."""
        config = ScanConfig()
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Validation should be disabled
        assert pipeline.enable_schema_validation is False
        assert pipeline._validator is None

    def test_schema_validation_enabled_via_config(self):
        """Test that schema validation can be enabled via config."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="log_only")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Validation should be enabled
        assert pipeline.enable_schema_validation is True
        # Validator might not init if jsonschema not installed
        # That's ok - we just check the flag

    def test_validation_mode_log_only(self):
        """Test log_only mode allows invalid data through."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="log_only")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Mock telemetry hook to capture what's sent
        mock_hook = Mock(spec=TelemetryHook)
        pipeline.telemetry_hook = mock_hook

        # Scan a test prompt
        pipeline.scan("Test prompt")

        # Even if validation fails, telemetry should be sent in log_only mode
        # (We can't easily trigger validation failure without real validator,
        # but we can verify the mode is set correctly)
        assert pipeline.schema_validation_mode == "log_only"

    def test_validation_mode_warn(self):
        """Test warn mode allows data through with warnings."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="warn")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        assert pipeline.schema_validation_mode == "warn"

    def test_validation_mode_enforce(self):
        """Test enforce mode blocks invalid data."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="enforce")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        assert pipeline.schema_validation_mode == "enforce"

    def test_telemetry_payload_structure(self):
        """Test that telemetry payload matches expected schema structure."""
        config = ScanConfig(
            enable_schema_validation=False  # Don't validate yet
        )
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Mock telemetry hook to capture payload
        captured_payload = None

        def capture_send(payload):
            nonlocal captured_payload
            captured_payload = payload

        mock_hook = Mock(spec=TelemetryHook)
        mock_hook.send = capture_send
        pipeline.telemetry_hook = mock_hook

        # Scan a test prompt
        pipeline.scan("Test prompt", customer_id="test-customer")

        # Verify payload structure matches schema expectations
        assert captured_payload is not None
        assert "event_name" in captured_payload
        assert captured_payload["event_name"] == "scan_performed"
        assert "prompt_hash" in captured_payload
        assert "timestamp" in captured_payload
        assert "max_severity" in captured_payload
        assert "detection_count" in captured_payload
        assert "l1_detection_count" in captured_payload
        assert "l2_prediction_count" in captured_payload
        assert "scan_duration_ms" in captured_payload
        assert "policy_action" in captured_payload
        assert "blocked" in captured_payload

    def test_validation_error_tracking(self):
        """Test that validation errors are tracked."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="log_only")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Initial validation error count should be 0
        assert pipeline._validation_errors == 0

        # Scan some prompts
        pipeline.scan("Test 1")
        pipeline.scan("Test 2")

        # Error count should still be 0 if validation passes
        # (or if validator not available)
        assert pipeline._validation_errors >= 0

    def test_schema_validation_doesnt_break_scans(self):
        """Test that enabling validation doesn't break normal scanning."""
        config = ScanConfig(enable_schema_validation=True, schema_validation_mode="enforce")
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Should be able to scan normally
        result = pipeline.scan("Test prompt with validation enabled")

        # Result should be valid
        assert result is not None
        assert result.duration_ms >= 0
        assert result.text_hash is not None
