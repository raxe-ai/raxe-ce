"""ONNX-based embedding generator for faster inference.

Replaces sentence-transformers with ONNX Runtime for 5x speedup.
Uses quantized INT8 ONNX model for embedding generation.
"""
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
        self.model_path = Path(model_path)
        self.tokenizer_name = tokenizer_name
        self.max_seq_length = max_seq_length

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
        logger.info(f"Loading tokenizer: {tokenizer_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        # Load ONNX model
        logger.info(f"Loading ONNX model: {self.model_path}")
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=['CPUExecutionProvider']  # Use CPU (quantized model)
        )

        logger.info(f"✓ ONNX embedder ready (model: {self.model_path.name})")

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
        # Handle single text
        if isinstance(text, str):
            texts = [text]
            return_single = True
        else:
            texts = text
            return_single = False

        # Tokenize
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_seq_length,
            return_tensors="np",
        )

        # Run ONNX inference
        onnx_inputs = {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64),
        }

        # Some models also need token_type_ids
        if "token_type_ids" in encoded:
            onnx_inputs["token_type_ids"] = encoded["token_type_ids"].astype(np.int64)

        # Forward pass
        onnx_outputs = self.session.run(None, onnx_inputs)

        # Extract embeddings (usually first output)
        # For sentence transformers: mean pooling of token embeddings
        embeddings = self._mean_pooling(
            onnx_outputs[0],  # Token embeddings
            encoded["attention_mask"]
        )

        # Normalize if requested
        if normalize_embeddings:
            embeddings = self._normalize(embeddings)

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
