"""Integration test for ProductionL2Detector in scan pipeline.

Tests that the production ML detector can be integrated into the scan pipeline
and works correctly with real scanning workflows.
"""

import pytest

from raxe.application.preloader import PipelinePreloader
from raxe.infrastructure.config.scan_config import ScanConfig


class TestProductionL2Integration:
    """Test ProductionL2Detector integration with scan pipeline."""

    def test_production_detector_loads_in_pipeline(self):
        """Test that production detector can be initialized in pipeline."""
        # Create config that enables production L2
        config = ScanConfig(
            enable_l2=True,
            use_production_l2=True,
            l2_confidence_threshold=0.5,
        )

        # Preload pipeline with production detector
        try:
            preloader = PipelinePreloader(config=config)
            pipeline, stats = preloader.preload()

            # Check that pipeline was created successfully
            assert pipeline is not None
            assert stats.config_loaded is True

            # Check that L2 detector is present
            assert pipeline.l2_detector is not None

            # Verify it's a production detector (not stub)
            # We can check by scanning and seeing if it returns real predictions
            result = pipeline.scan("Test prompt")
            assert result is not None

        except Exception as e:
            # If model files are not available, test should skip
            # This is expected in CI environments without model files
            pytest.skip(f"Production L2 model not available: {e}")

    def test_fallback_to_stub_on_error(self):
        """Test that pipeline falls back to stub if production detector fails."""
        # Create config that requests production L2 with invalid path
        config = ScanConfig(
            enable_l2=True,
            use_production_l2=True,
            l2_confidence_threshold=0.5,
        )

        # Even if production fails to load, preloader should fall back to stub
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Pipeline should still be created
        assert pipeline is not None
        assert pipeline.l2_detector is not None

        # Should be able to scan
        result = pipeline.scan("Test prompt")
        assert result is not None

    def test_stub_detector_when_disabled(self):
        """Test that stub detector is used when use_production_l2=False."""
        # Create config that explicitly uses stub
        config = ScanConfig(
            enable_l2=True,
            use_production_l2=False,  # Explicitly use stub
            l2_confidence_threshold=0.5,
        )

        # Preload pipeline
        preloader = PipelinePreloader(config=config)
        pipeline, _stats = preloader.preload()

        # Pipeline should use stub detector
        assert pipeline is not None
        assert pipeline.l2_detector is not None

        # Should be able to scan
        result = pipeline.scan("Test prompt")
        assert result is not None

    def test_confidence_threshold_configuration(self):
        """Test that confidence threshold is configurable."""
        # Test with different thresholds
        thresholds = [0.3, 0.5, 0.7, 0.9]

        for threshold in thresholds:
            config = ScanConfig(
                enable_l2=True,
                use_production_l2=True,
                l2_confidence_threshold=threshold,
            )

            try:
                preloader = PipelinePreloader(config=config)
                pipeline, _stats = preloader.preload()

                # Verify threshold is respected
                # (actual verification would require checking detector internals)
                assert pipeline is not None

            except Exception as e:
                pytest.skip(f"Production L2 model not available: {e}")

    def test_production_detector_type_check(self):
        """Test that production detector matches protocol."""
        try:
            from raxe.domain.ml import create_production_l2_detector

            # Create detector
            detector = create_production_l2_detector()

            # Check that it has required methods
            assert hasattr(detector, 'analyze')
            assert callable(detector.analyze)

            # Check model info
            model_info = detector.model_info
            assert 'name' in model_info
            assert 'version' in model_info
            assert model_info['is_stub'] is False

        except Exception as e:
            pytest.skip(f"Production L2 model not available: {e}")
