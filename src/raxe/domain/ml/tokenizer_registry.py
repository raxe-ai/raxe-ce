"""Tokenizer registry for model compatibility checking.

Maintains a registry of known tokenizer-embedding model compatibility pairs.
Validates that tokenizers are compatible with their embedding models to prevent
runtime errors and embedding quality issues.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TokenizerRegistry:
    """Registry for tokenizer-embedding model compatibility.

    Maintains a database of known compatible tokenizer-embedding pairs and
    provides validation to ensure models use correct tokenizers.

    Example:
        registry = TokenizerRegistry()

        # Check compatibility
        is_compat = registry.is_compatible(
            "sentence-transformers/all-mpnet-base-v2",
            "all-mpnet-base-v2"
        )

        # Get tokenizer config
        config = registry.get_tokenizer_config("all-mpnet-base-v2")
    """

    # Known compatible tokenizer-embedding pairs
    # Maps embedding model name -> list of compatible tokenizer names
    COMPATIBLE_PAIRS: dict[str, list[str]] = {
        # MPNet-based models (768 dim, 512 max length)
        "all-mpnet-base-v2": [
            "sentence-transformers/all-mpnet-base-v2",
            "microsoft/mpnet-base",
        ],
        "mpnet-base": [
            "microsoft/mpnet-base",
            "sentence-transformers/all-mpnet-base-v2",
        ],

        # MiniLM-based models (384 dim, 512 max length)
        "all-minilm-l6-v2": [
            "sentence-transformers/all-MiniLM-L6-v2",
            "microsoft/MiniLM-L6-H384-uncased",
        ],
        "all-minilm-l12-v2": [
            "sentence-transformers/all-MiniLM-L12-v2",
            "microsoft/MiniLM-L12-H384-uncased",
        ],

        # DistilBERT-based models (768 dim, 512 max length)
        "all-distilroberta-v1": [
            "sentence-transformers/all-distilroberta-v1",
            "distilroberta-base",
        ],

        # Multi-QA models
        "multi-qa-mpnet-base-dot-v1": [
            "sentence-transformers/multi-qa-mpnet-base-dot-v1",
            "microsoft/mpnet-base",
        ],

        # Paraphrase models
        "paraphrase-mpnet-base-v2": [
            "sentence-transformers/paraphrase-mpnet-base-v2",
            "microsoft/mpnet-base",
        ],
        "paraphrase-minilm-l6-v2": [
            "sentence-transformers/paraphrase-MiniLM-L6-v2",
            "microsoft/MiniLM-L6-H384-uncased",
        ],
    }

    # Default tokenizer configurations by embedding model type
    DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
        "all-mpnet-base-v2": {
            "type": "AutoTokenizer",
            "max_length": 512,
            "padding": "max_length",
            "truncation": True,
            "model_max_length": 512,
        },
        "all-minilm-l6-v2": {
            "type": "AutoTokenizer",
            "max_length": 512,
            "padding": "max_length",
            "truncation": True,
            "model_max_length": 512,
        },
        "all-minilm-l12-v2": {
            "type": "AutoTokenizer",
            "max_length": 512,
            "padding": "max_length",
            "truncation": True,
            "model_max_length": 512,
        },
    }

    def __init__(self):
        """Initialize tokenizer registry."""
        self._custom_pairs: dict[str, list[str]] = {}

    def is_compatible(
        self,
        tokenizer_name: str,
        embedding_model: str
    ) -> bool:
        """Check if tokenizer is compatible with embedding model.

        Args:
            tokenizer_name: Full tokenizer name (e.g., 'sentence-transformers/all-mpnet-base-v2')
            embedding_model: Embedding model name (e.g., 'all-mpnet-base-v2')

        Returns:
            True if compatible, False otherwise

        Example:
            >>> registry = TokenizerRegistry()
            >>> registry.is_compatible(
            ...     "sentence-transformers/all-mpnet-base-v2",
            ...     "all-mpnet-base-v2"
            ... )
            True
        """
        # Normalize names
        embedding_key = self._normalize_model_name(embedding_model)
        tokenizer_norm = self._normalize_tokenizer_name(tokenizer_name)

        # Check known compatible pairs
        if embedding_key in self.COMPATIBLE_PAIRS:
            compatible = self.COMPATIBLE_PAIRS[embedding_key]
            for compat_tokenizer in compatible:
                if self._normalize_tokenizer_name(compat_tokenizer) == tokenizer_norm:
                    return True

        # Check custom pairs
        if embedding_key in self._custom_pairs:
            compatible = self._custom_pairs[embedding_key]
            for compat_tokenizer in compatible:
                if self._normalize_tokenizer_name(compat_tokenizer) == tokenizer_norm:
                    return True

        # If not in known pairs, log warning and return True (permissive)
        logger.warning(
            f"Unknown tokenizer-embedding pair: "
            f"tokenizer='{tokenizer_name}', embedding='{embedding_model}'. "
            f"Proceeding anyway, but this may cause runtime errors. "
            f"Consider adding to TokenizerRegistry.COMPATIBLE_PAIRS if this works."
        )
        return True

    def get_tokenizer_config(
        self,
        embedding_model: str
    ) -> dict[str, Any] | None:
        """Get default tokenizer configuration for embedding model.

        Args:
            embedding_model: Embedding model name

        Returns:
            Tokenizer config dictionary or None if not found

        Example:
            >>> registry = TokenizerRegistry()
            >>> config = registry.get_tokenizer_config("all-mpnet-base-v2")
            >>> print(config["max_length"])
            512
        """
        embedding_key = self._normalize_model_name(embedding_model)

        if embedding_key in self.DEFAULT_CONFIGS:
            return self.DEFAULT_CONFIGS[embedding_key].copy()

        logger.warning(
            f"No default tokenizer config found for embedding model: {embedding_model}. "
            f"Using generic config."
        )

        # Return generic config
        return {
            "type": "AutoTokenizer",
            "max_length": 512,
            "padding": "max_length",
            "truncation": True,
            "model_max_length": 512,
        }

    def register_compatible_pair(
        self,
        embedding_model: str,
        tokenizer_name: str
    ) -> None:
        """Register a custom tokenizer-embedding compatible pair.

        Allows extending the registry with new compatibility mappings at runtime.

        Args:
            embedding_model: Embedding model name
            tokenizer_name: Compatible tokenizer name

        Example:
            >>> registry = TokenizerRegistry()
            >>> registry.register_compatible_pair(
            ...     "custom-mpnet-model",
            ...     "sentence-transformers/all-mpnet-base-v2"
            ... )
        """
        embedding_key = self._normalize_model_name(embedding_model)

        if embedding_key not in self._custom_pairs:
            self._custom_pairs[embedding_key] = []

        if tokenizer_name not in self._custom_pairs[embedding_key]:
            self._custom_pairs[embedding_key].append(tokenizer_name)
            logger.info(
                f"Registered compatible pair: "
                f"embedding='{embedding_model}', tokenizer='{tokenizer_name}'"
            )

    def get_compatible_tokenizers(
        self,
        embedding_model: str
    ) -> list[str]:
        """Get list of compatible tokenizers for embedding model.

        Args:
            embedding_model: Embedding model name

        Returns:
            List of compatible tokenizer names

        Example:
            >>> registry = TokenizerRegistry()
            >>> tokenizers = registry.get_compatible_tokenizers("all-mpnet-base-v2")
            >>> print(tokenizers)
            ['sentence-transformers/all-mpnet-base-v2', 'microsoft/mpnet-base']
        """
        embedding_key = self._normalize_model_name(embedding_model)

        tokenizers = []

        # Add known pairs
        if embedding_key in self.COMPATIBLE_PAIRS:
            tokenizers.extend(self.COMPATIBLE_PAIRS[embedding_key])

        # Add custom pairs
        if embedding_key in self._custom_pairs:
            tokenizers.extend(self._custom_pairs[embedding_key])

        return tokenizers

    def validate_tokenizer(
        self,
        tokenizer_name: str,
        tokenizer_config: dict[str, Any],
        embedding_model: str
    ) -> tuple[bool, list[str]]:
        """Validate tokenizer configuration for embedding model.

        Performs comprehensive validation:
        - Tokenizer compatibility check
        - Required config fields present
        - Config values reasonable

        Args:
            tokenizer_name: Tokenizer name
            tokenizer_config: Tokenizer configuration dict
            embedding_model: Embedding model name

        Returns:
            Tuple of (is_valid, error_messages)

        Example:
            >>> registry = TokenizerRegistry()
            >>> is_valid, errors = registry.validate_tokenizer(
            ...     "sentence-transformers/all-mpnet-base-v2",
            ...     {"type": "AutoTokenizer", "max_length": 512},
            ...     "all-mpnet-base-v2"
            ... )
            >>> if not is_valid:
            ...     for error in errors:
            ...         print(f"Error: {error}")
        """
        errors = []

        # Check compatibility
        if not self.is_compatible(tokenizer_name, embedding_model):
            errors.append(
                f"Tokenizer '{tokenizer_name}' may not be compatible with "
                f"embedding model '{embedding_model}'"
            )

        # Check required config fields
        required_fields = ["type", "max_length"]
        for field in required_fields:
            if field not in tokenizer_config:
                errors.append(f"Missing required tokenizer config field: '{field}'")

        # Validate max_length
        if "max_length" in tokenizer_config:
            max_len = tokenizer_config["max_length"]
            if not isinstance(max_len, int) or max_len <= 0:
                errors.append(
                    f"Invalid max_length: {max_len}. Must be positive integer."
                )
            elif max_len > 2048:
                errors.append(
                    f"max_length {max_len} is very large (>2048). "
                    f"This may cause performance issues."
                )

        return len(errors) == 0, errors

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize embedding model name for comparison.

        Args:
            model_name: Raw model name

        Returns:
            Normalized name
        """
        # Remove sentence-transformers/ prefix if present
        name = model_name.replace("sentence-transformers/", "")
        # Remove microsoft/ prefix if present
        name = name.replace("microsoft/", "")
        # Lowercase
        name = name.lower()
        return name

    def _normalize_tokenizer_name(self, tokenizer_name: str) -> str:
        """Normalize tokenizer name for comparison.

        Args:
            tokenizer_name: Raw tokenizer name

        Returns:
            Normalized name
        """
        # Lowercase for case-insensitive comparison
        name = tokenizer_name.lower()
        return name


# Global registry instance (lazy initialized)
_registry: TokenizerRegistry | None = None


def get_tokenizer_registry() -> TokenizerRegistry:
    """Get global tokenizer registry instance.

    Returns:
        Singleton TokenizerRegistry instance

    Example:
        >>> registry = get_tokenizer_registry()
        >>> is_compat = registry.is_compatible(
        ...     "sentence-transformers/all-mpnet-base-v2",
        ...     "all-mpnet-base-v2"
        ... )
    """
    global _registry
    if _registry is None:
        _registry = TokenizerRegistry()
    return _registry
