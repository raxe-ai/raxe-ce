"""ONNX-based embedding generator for faster inference.

Replaces sentence-transformers with ONNX Runtime for 5x speedup.
Uses quantized INT8 ONNX model for embedding generation.

Performance:
- Load time: ~500ms (vs ~5s for sentence-transformers)
- Inference time: ~5-10ms per text
- Model size: 106MB (quantized INT8)
"""
import time
import numpy as np
from pathlib import Path
from typing import List
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class ONNXEmbedder:
    """
    ONNX-based embedder for fast text embedding generation.

    Uses ONNX Runtime with quantized INT8 models for 5x speedup
    compared to sentence-transformers.

    Example:
        embedder = ONNXEmbedder(
            model_path="models/quantized_int8.onnx",
            tokenizer_name="sentence-transformers/all-mpnet-base-v2"
        )

        embedding = embedder.encode("Ignore all instructions")
        # 5x faster than sentence-transformers!
    """

    def __init__(
        self,
        model_path: str | Path,
        tokenizer_name: str = "sentence-transformers/all-mpnet-base-v2",
        max_seq_length: int = 512,
    ):
        """
        Initialize ONNX embedder.

        Args:
            model_path: Path to quantized ONNX model file
            tokenizer_name: Hugging Face tokenizer name
            max_seq_length: Maximum sequence length

        Raises:
            ImportError: If onnxruntime or transformers not installed
            FileNotFoundError: If ONNX model not found
        """
        init_start = time.perf_counter()

        self.model_path = Path(model_path)
        self.tokenizer_name = tokenizer_name
        self.max_seq_length = max_seq_length

        # Performance tracking
        self._init_time_ms: float = 0.0
        self._total_encode_time_ms: float = 0.0
        self._encode_count: int = 0

        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {self.model_path}")

        # Import dependencies (lazy)
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ImportError(
                "ONNX embedder requires onnxruntime. "
                "Install with: pip install onnxruntime"
            ) from e

        try:
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "ONNX embedder requires transformers. "
                "Install with: pip install transformers"
            ) from e

        # Load tokenizer
        tokenizer_start = time.perf_counter()
        logger.info(f"Loading tokenizer: {tokenizer_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        tokenizer_time_ms = (time.perf_counter() - tokenizer_start) * 1000

        # Load ONNX model
        model_start = time.perf_counter()
        logger.info(f"Loading ONNX model: {self.model_path}")
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=['CPUExecutionProvider']  # Use CPU (quantized model)
        )
        model_time_ms = (time.perf_counter() - model_start) * 1000

        # Total initialization time
        self._init_time_ms = (time.perf_counter() - init_start) * 1000

        # Get model size
        model_size_mb = self.model_path.stat().st_size / (1024 * 1024)

        logger.info(
            "onnx_embedder_initialized",
            model=self.model_path.name,
            model_size_mb=round(model_size_mb, 2),
            tokenizer=tokenizer_name,
            tokenizer_load_ms=round(tokenizer_time_ms, 2),
            model_load_ms=round(model_time_ms, 2),
            total_init_ms=round(self._init_time_ms, 2),
        )

    def encode(
        self,
        text: str | List[str],
        normalize_embeddings: bool = True,
        batch_size: int = 32,
    ) -> np.ndarray:
        """
        Generate embeddings for text.

        Args:
            text: Single text or list of texts
            normalize_embeddings: Whether to L2 normalize embeddings
            batch_size: Batch size for processing

        Returns:
            Embedding vector(s) as numpy array

        Example:
            # Single text
            emb = embedder.encode("test")  # Shape: (768,)

            # Multiple texts
            embs = embedder.encode(["test1", "test2"])  # Shape: (2, 768)
        """
        encode_start = time.perf_counter()

        # Handle single text
        if isinstance(text, str):
            texts = [text]
            return_single = True
        else:
            texts = text
            return_single = False

        # Tokenize
        tokenize_start = time.perf_counter()
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_seq_length,
            return_tensors="np",
        )
        tokenize_time_ms = (time.perf_counter() - tokenize_start) * 1000

        # Run ONNX inference
        inference_start = time.perf_counter()
        onnx_inputs = {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64),
        }

        # Some models also need token_type_ids
        if "token_type_ids" in encoded:
            onnx_inputs["token_type_ids"] = encoded["token_type_ids"].astype(np.int64)

        # Forward pass
        onnx_outputs = self.session.run(None, onnx_inputs)
        inference_time_ms = (time.perf_counter() - inference_start) * 1000

        # Extract embeddings (usually first output)
        # For sentence transformers: mean pooling of token embeddings
        pooling_start = time.perf_counter()
        embeddings = self._mean_pooling(
            onnx_outputs[0],  # Token embeddings
            encoded["attention_mask"]
        )

        # Normalize if requested
        if normalize_embeddings:
            embeddings = self._normalize(embeddings)
        pooling_time_ms = (time.perf_counter() - pooling_start) * 1000

        # Track performance
        total_encode_time_ms = (time.perf_counter() - encode_start) * 1000
        self._total_encode_time_ms += total_encode_time_ms
        self._encode_count += 1

        # Log detailed timing for first few calls (debugging)
        if self._encode_count <= 3:
            logger.debug(
                "onnx_encode_timing",
                call_number=self._encode_count,
                num_texts=len(texts),
                tokenize_ms=round(tokenize_time_ms, 2),
                inference_ms=round(inference_time_ms, 2),
                pooling_ms=round(pooling_time_ms, 2),
                total_ms=round(total_encode_time_ms, 2),
            )

        # Return single embedding or batch
        if return_single:
            return embeddings[0]
        return embeddings

    def _mean_pooling(self, token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        """
        Mean pooling of token embeddings with attention mask.

        This matches sentence-transformers pooling strategy.
        """
        # Expand mask to match embedding dimensions
        input_mask_expanded = np.expand_dims(attention_mask, -1).astype(float)
        input_mask_expanded = np.broadcast_to(
            input_mask_expanded,
            token_embeddings.shape
        )

        # Sum embeddings
        sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)

        # Sum mask
        sum_mask = np.sum(input_mask_expanded, axis=1)
        sum_mask = np.clip(sum_mask, a_min=1e-9, a_max=None)  # Avoid division by zero

        # Mean pooling
        return sum_embeddings / sum_mask

    def _normalize(self, embeddings: np.ndarray) -> np.ndarray:
        """L2 normalize embeddings."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.clip(norms, a_min=1e-9, a_max=None)  # Avoid division by zero
        return embeddings / norms

    @property
    def performance_stats(self) -> dict:
        """Get performance statistics.

        Returns:
            Dictionary with performance metrics:
                - init_time_ms: Initialization time
                - encode_count: Number of encode calls
                - total_encode_time_ms: Total time spent encoding
                - avg_encode_time_ms: Average encode time
                - model_size_mb: Model file size

        Example:
            embedder = ONNXEmbedder("model.onnx")
            embedder.encode("test")
            stats = embedder.performance_stats
            print(f"Avg encode time: {stats['avg_encode_time_ms']}ms")
        """
        avg_encode_time = (
            self._total_encode_time_ms / self._encode_count
            if self._encode_count > 0
            else 0.0
        )

        return {
            "init_time_ms": round(self._init_time_ms, 2),
            "encode_count": self._encode_count,
            "total_encode_time_ms": round(self._total_encode_time_ms, 2),
            "avg_encode_time_ms": round(avg_encode_time, 2),
            "model_size_mb": round(self.model_path.stat().st_size / (1024 * 1024), 2),
        }


def create_onnx_embedder(
    model_path: str | Path,
    tokenizer_name: str = "sentence-transformers/all-mpnet-base-v2",
) -> ONNXEmbedder:
    """
    Factory function to create ONNX embedder.

    Args:
        model_path: Path to ONNX model
        tokenizer_name: Tokenizer name

    Returns:
        ONNXEmbedder instance

    Example:
        embedder = create_onnx_embedder("models/quantized.onnx")
        embedding = embedder.encode("test")
    """
    return ONNXEmbedder(model_path=model_path, tokenizer_name=tokenizer_name)
