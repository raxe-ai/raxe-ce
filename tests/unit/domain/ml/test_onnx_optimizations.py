"""
Tests for ONNX Runtime optimizations in FolderL2Detector.

Validates that session options and execution providers are configured correctly
for optimal inference performance.

Test Coverage:
- Session options configuration (graph optimization, threading)
- Execution provider fallback chain
- Provider selection logging
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestONNXSessionOptions:
    """Tests for ONNX session options configuration."""

    def test_session_options_graph_optimization_level(self) -> None:
        """Test that graph optimization is set to ORT_ENABLE_ALL."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            # Setup mock
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            # Create a minimal mock detector to test the method
            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            # Call the method
            result = detector._create_session_options()

            # Verify optimization level was set
            assert result.graph_optimization_level == ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    def test_session_options_log_severity_level(self) -> None:
        """Test that log_severity_level is set to ERROR (3) to suppress warnings."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            # Setup mock
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            # Create a minimal mock detector to test the method
            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            # Call the method
            result = detector._create_session_options()

            # Verify log severity is set to ERROR (3) to suppress warnings
            assert result.log_severity_level == 3

    def test_session_options_thread_configuration(self) -> None:
        """Test that thread counts are configured correctly."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            result = detector._create_session_options()

            # intra_op should be min(4, cpu_count)
            cpu_count = os.cpu_count() or 4
            expected_intra = min(4, cpu_count)
            assert result.intra_op_num_threads == expected_intra

            # inter_op should be 1 for sequential execution
            assert result.inter_op_num_threads == 1

    def test_session_options_memory_optimizations(self) -> None:
        """Test that memory optimizations are enabled."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            result = detector._create_session_options()

            # Memory optimizations should be enabled
            assert result.enable_mem_pattern is True
            assert result.enable_cpu_mem_arena is True


class TestExecutionProviderFallback:
    """Tests for execution provider fallback chain."""

    def test_int8_model_prefers_cpu_over_coreml(self) -> None:
        """Test that INT8 models prefer CPU over CoreML for better performance."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            # Mock all providers being available
            ort.get_available_providers.return_value = [
                "CPUExecutionProvider",
                "CUDAExecutionProvider",
                "CoreMLExecutionProvider",
            ]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            # INT8 model path - should prefer CPU
            detector.model_dir = Path("/fake/threat_classifier_int8_deploy")
            detector.providers = ["CPUExecutionProvider"]  # Default

            result = detector._get_execution_providers()

            # INT8 models should prefer CPU (3-4x faster than CoreML)
            assert result[0] == "CPUExecutionProvider"
            # CoreML should NOT be in the chain for INT8 models
            assert "CoreMLExecutionProvider" not in result

    def test_fp16_model_uses_coreml(self) -> None:
        """Test that FP16/FP32 models use CoreML for acceleration."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            # Mock all providers being available
            ort.get_available_providers.return_value = [
                "CPUExecutionProvider",
                "CUDAExecutionProvider",
                "CoreMLExecutionProvider",
            ]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            # FP16 model path - should use CoreML
            detector.model_dir = Path("/fake/threat_classifier_fp16_deploy")
            detector.providers = ["CPUExecutionProvider"]  # Default

            result = detector._get_execution_providers()

            # FP16 models should prefer CoreML for acceleration
            assert result[0] == "CoreMLExecutionProvider"
            assert result[1] == "CUDAExecutionProvider"
            assert result[-1] == "CPUExecutionProvider"

    def test_cpu_always_included_as_fallback(self) -> None:
        """Test that CPU is always included as last fallback."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            # Only exotic provider available (edge case)
            ort.get_available_providers.return_value = ["SomeExoticProvider"]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            result = detector._get_execution_providers()

            # CPU should always be present
            assert "CPUExecutionProvider" in result
            assert result[-1] == "CPUExecutionProvider"

    def test_user_specified_providers_take_priority(self) -> None:
        """Test that user-specified providers override auto-detection."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.get_available_providers.return_value = [
                "CPUExecutionProvider",
                "CUDAExecutionProvider",
            ]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            # User explicitly specifies CUDA only
            detector.providers = ["CUDAExecutionProvider"]

            result = detector._get_execution_providers()

            # Should use user's specification
            assert result == ["CUDAExecutionProvider"]

    def test_default_cpu_provider_triggers_auto_detection_for_fp16(self) -> None:
        """Test that default CPU provider triggers automatic fallback chain for FP16."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.get_available_providers.return_value = [
                "CPUExecutionProvider",
                "CoreMLExecutionProvider",
            ]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            # FP16 model - should auto-detect and use CoreML
            detector.model_dir = Path("/fake/threat_classifier_fp16_deploy")
            # Default setting
            detector.providers = ["CPUExecutionProvider"]

            result = detector._get_execution_providers()

            # FP16 models should auto-detect and use CoreML
            assert "CoreMLExecutionProvider" in result

    def test_default_cpu_provider_uses_cpu_for_int8(self) -> None:
        """Test that INT8 models stay with CPU even when CoreML is available."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.get_available_providers.return_value = [
                "CPUExecutionProvider",
                "CoreMLExecutionProvider",
            ]

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            # INT8 model - should NOT use CoreML
            detector.model_dir = Path("/fake/threat_classifier_int8_deploy")
            # Default setting
            detector.providers = ["CPUExecutionProvider"]

            result = detector._get_execution_providers()

            # INT8 models should NOT use CoreML (CPU is 3-4x faster)
            assert "CoreMLExecutionProvider" not in result
            assert result[0] == "CPUExecutionProvider"


class TestInferenceSessionCreation:
    """Tests for optimized inference session creation."""

    def test_session_created_with_options_and_providers(self) -> None:
        """Test that session is created with session options and providers."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            ort.get_available_providers.return_value = ["CPUExecutionProvider"]

            mock_session = MagicMock()
            mock_session.get_providers.return_value = ["CPUExecutionProvider"]
            ort.InferenceSession.return_value = mock_session

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            result = detector._create_inference_session(
                Path("/fake/model.onnx"),
                "test_model"
            )

            # Verify InferenceSession was called with sess_options and providers
            call_kwargs = ort.InferenceSession.call_args.kwargs
            assert "sess_options" in call_kwargs
            assert "providers" in call_kwargs

    def test_session_logs_selected_provider(self) -> None:
        """Test that the selected provider is logged for debugging."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            ort.get_available_providers.return_value = ["CPUExecutionProvider"]

            mock_session = MagicMock()
            mock_session.get_providers.return_value = ["CPUExecutionProvider"]
            ort.InferenceSession.return_value = mock_session

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            with patch("raxe.domain.ml.folder_detector.logger") as mock_logger:
                detector._create_inference_session(
                    Path("/fake/model.onnx"),
                    "test_model"
                )

                # Verify logging was called with provider info
                mock_logger.info.assert_called()
                call_kwargs = mock_logger.info.call_args.kwargs
                assert "selected_provider" in call_kwargs
                assert call_kwargs["selected_provider"] == "CPUExecutionProvider"


class TestOptimizationPerformance:
    """Performance-related tests for ONNX optimizations."""

    def test_intra_op_threads_capped_at_four(self) -> None:
        """Test that intra_op threads are capped at 4 to avoid overhead."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            # Mock high CPU count
            with patch("os.cpu_count", return_value=32):
                result = detector._create_session_options()

                # Should still be capped at 4
                assert result.intra_op_num_threads == 4

    def test_handles_none_cpu_count_gracefully(self) -> None:
        """Test graceful handling when os.cpu_count() returns None."""
        with patch.dict("sys.modules", {"onnxruntime": MagicMock()}):
            import onnxruntime as ort

            ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
            mock_session_options = MagicMock()
            ort.SessionOptions.return_value = mock_session_options

            from raxe.domain.ml.folder_detector import FolderL2Detector

            detector = object.__new__(FolderL2Detector)
            detector.model_dir = Path("/fake/path")
            detector.providers = ["CPUExecutionProvider"]

            # Mock None CPU count (can happen in some environments)
            with patch("os.cpu_count", return_value=None):
                result = detector._create_session_options()

                # Should use fallback of 4
                assert result.intra_op_num_threads == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
