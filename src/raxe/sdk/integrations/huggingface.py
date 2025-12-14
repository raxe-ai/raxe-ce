"""Hugging Face integration for RAXE scanning.

Provides a wrapper for Hugging Face transformers pipeline that automatically
scans inputs and outputs for security threats.

This integration works with:
    - text-generation pipelines
    - text2text-generation pipelines
    - conversational pipelines
    - question-answering pipelines
    - Any pipeline that processes text

Usage:
    from raxe.sdk.integrations import RaxePipeline

    # Wrap any Hugging Face pipeline
    pipe = RaxePipeline(
        task="text-generation",
        model="gpt2"
    )

    # All inputs and outputs automatically scanned
    result = pipe("Once upon a time")
"""
import logging
from typing import Any

from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import SecurityException

logger = logging.getLogger(__name__)


class RaxePipeline:
    """Protected Hugging Face pipeline with automatic RAXE scanning.

    This wrapper wraps any Hugging Face transformers pipeline and
    automatically scans all text inputs and outputs for security threats.

    Works with:
        - text-generation
        - text2text-generation
        - conversational
        - question-answering
        - summarization
        - translation
        - Any text-based pipeline

    Attributes:
        raxe: Raxe client instance for scanning
        pipeline: Underlying Hugging Face pipeline
        raxe_block_on_input_threats: Block on input threats
        raxe_block_on_output_threats: Block on output threats
        task: Pipeline task name

    Example:
        >>> from raxe.sdk.integrations import RaxePipeline
        >>>
        >>> # Text generation
        >>> pipe = RaxePipeline(
        ...     task="text-generation",
        ...     model="gpt2"
        ... )
        >>> result = pipe("Once upon a time")
        >>>
        >>> # Question answering
        >>> qa_pipe = RaxePipeline(
        ...     task="question-answering",
        ...     model="distilbert-base-cased-distilled-squad"
        ... )
        >>> result = qa_pipe(
        ...     question="What is AI?",
        ...     context="AI is artificial intelligence..."
        ... )
    """

    def __init__(
        self,
        task: str,
        model: str | None = None,
        *,
        raxe: Raxe | None = None,
        raxe_block_on_input_threats: bool = True,
        raxe_block_on_output_threats: bool = False,
        pipeline_kwargs: dict[str, Any] | None = None,
        **kwargs
    ):
        """Initialize RAXE-protected Hugging Face pipeline.

        Args:
            task: Pipeline task (text-generation, question-answering, etc.)
            model: Model name or path (optional, uses task default if None)
            raxe: Optional Raxe instance (creates default if None)
            raxe_block_on_input_threats: Block on input threats (default: True)
            raxe_block_on_output_threats: Block on output threats (default: False)
            pipeline_kwargs: Additional kwargs for pipeline creation
            **kwargs: Additional pipeline parameters

        Example:
            # Basic usage
            pipe = RaxePipeline(
                task="text-generation",
                model="gpt2"
            )

            # With custom Raxe client
            raxe = Raxe(telemetry=False)
            pipe = RaxePipeline(
                task="text-generation",
                model="gpt2",
                raxe=raxe
            )

            # Monitoring mode only
            pipe = RaxePipeline(
                task="text-generation",
                model="gpt2",
                raxe_block_on_input_threats=False
            )

        Raises:
            ImportError: If transformers package not installed
        """
        # Try to import transformers
        try:
            from transformers import pipeline
        except ImportError as e:
            raise ImportError(
                "transformers package is required for RaxePipeline. "
                "Install with: pip install transformers"
            ) from e

        # Create Hugging Face pipeline
        pipeline_kwargs = pipeline_kwargs or {}
        if model:
            pipeline_kwargs["model"] = model

        self.pipeline = pipeline(task, **pipeline_kwargs, **kwargs)
        self.task = task

        # Create or use provided Raxe client
        if raxe is None:
            raxe = Raxe()

        self.raxe = raxe
        self.raxe_block_on_input_threats = raxe_block_on_input_threats
        self.raxe_block_on_output_threats = raxe_block_on_output_threats

        logger.debug(
            f"RaxePipeline initialized: task={task}, model={model}, "
            f"block_input={raxe_block_on_input_threats}, "
            f"block_output={raxe_block_on_output_threats}"
        )

    def __call__(self, *args, **kwargs) -> Any:
        """Run pipeline with automatic scanning.

        Scans inputs before processing and outputs after processing.

        Args:
            *args: Positional arguments for pipeline
            **kwargs: Keyword arguments for pipeline

        Returns:
            Pipeline output (format depends on task)

        Raises:
            SecurityException: If threat detected and blocking enabled

        Example:
            >>> pipe = RaxePipeline("text-generation", model="gpt2")
            >>> result = pipe("Once upon a time")
            >>> print(result[0]["generated_text"])
        """
        # Scan inputs
        self._scan_inputs(args, kwargs)

        # Run pipeline
        result = self.pipeline(*args, **kwargs)

        # Scan outputs
        if self.raxe_block_on_output_threats or self.raxe.config.telemetry.enabled:
            self._scan_outputs(result)

        return result

    def _scan_inputs(self, args: tuple, kwargs: dict[str, Any]):
        """Scan pipeline inputs for threats.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        # Extract text inputs based on task
        texts = self._extract_input_texts(args, kwargs)

        for idx, text in enumerate(texts):
            if not text:
                continue

            try:
                result = self.raxe.scan(
                    text,
                    block_on_threat=self.raxe_block_on_input_threats,
                )

                if result.has_threats:
                    logger.warning(
                        f"Threat detected in HuggingFace input {idx + 1}/{len(texts)}: "
                        f"{result.severity} severity "
                        f"(block={self.raxe_block_on_input_threats})"
                    )

            except SecurityException:
                logger.error(
                    f"Blocked HuggingFace input {idx + 1}/{len(texts)} "
                    f"due to security threat"
                )
                raise

    def _scan_outputs(self, outputs: Any):
        """Scan pipeline outputs for threats.

        Args:
            outputs: Pipeline outputs (format varies by task)

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        # Extract text outputs based on task
        texts = self._extract_output_texts(outputs)

        for idx, text in enumerate(texts):
            if not text:
                continue

            try:
                result = self.raxe.scan(
                    text,
                    block_on_threat=self.raxe_block_on_output_threats,
                )

                if result.has_threats:
                    logger.warning(
                        f"Threat detected in HuggingFace output {idx + 1}/{len(texts)}: "
                        f"{result.severity} severity "
                        f"(block={self.raxe_block_on_output_threats})"
                    )

            except SecurityException:
                logger.error(
                    f"Blocked HuggingFace output {idx + 1}/{len(texts)} "
                    f"due to security threat"
                )
                raise

    def _extract_input_texts(
        self,
        args: tuple,
        kwargs: dict[str, Any]
    ) -> list[str]:
        """Extract text strings from pipeline inputs.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            List of text strings to scan
        """
        texts: list[str] = []

        # Text generation, summarization, etc. - first arg is text
        if self.task in [
            "text-generation",
            "text2text-generation",
            "summarization",
            "translation",
        ]:
            if args and isinstance(args[0], str):
                texts.append(args[0])
            elif "text" in kwargs:
                texts.append(kwargs["text"])
            elif args and isinstance(args[0], list):
                # Batch input
                texts.extend([t for t in args[0] if isinstance(t, str)])

        # Question answering - question and context
        elif self.task == "question-answering":
            if "question" in kwargs:
                texts.append(kwargs["question"])
            if "context" in kwargs:
                texts.append(kwargs["context"])

        # Conversational - conversation history
        elif self.task == "conversational":
            if args and hasattr(args[0], "messages"):
                for msg in args[0].messages:
                    if isinstance(msg, str):
                        texts.append(msg)
                    elif isinstance(msg, dict) and "text" in msg:
                        texts.append(msg["text"])

        # Generic fallback - scan all string arguments
        else:
            for arg in args:
                if isinstance(arg, str):
                    texts.append(arg)
            for value in kwargs.values():
                if isinstance(value, str):
                    texts.append(value)

        return [text for text in texts if text]

    def _extract_output_texts(self, outputs: Any) -> list[str]:
        """Extract text strings from pipeline outputs.

        Args:
            outputs: Pipeline outputs (format varies by task)

        Returns:
            List of text strings to scan
        """
        texts: list[str] = []

        # Handle list of outputs
        if isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, str):
                    texts.append(output)
                elif isinstance(output, dict):
                    # Text generation
                    if "generated_text" in output:
                        texts.append(output["generated_text"])
                    # Summarization, translation
                    elif "summary_text" in output:
                        texts.append(output["summary_text"])
                    elif "translation_text" in output:
                        texts.append(output["translation_text"])
                    # Question answering
                    elif "answer" in output:
                        texts.append(output["answer"])
                    # Generic
                    elif "text" in output:
                        texts.append(output["text"])

        # Handle single dict output
        elif isinstance(outputs, dict):
            if "generated_text" in outputs:
                texts.append(outputs["generated_text"])
            elif "summary_text" in outputs:
                texts.append(outputs["summary_text"])
            elif "translation_text" in outputs:
                texts.append(outputs["translation_text"])
            elif "answer" in outputs:
                texts.append(outputs["answer"])
            elif "text" in outputs:
                texts.append(outputs["text"])

        # Handle conversational output
        elif hasattr(outputs, "generated_responses"):
            texts.extend(outputs.generated_responses)

        # Handle string output
        elif isinstance(outputs, str):
            texts.append(outputs)

        return [text for text in texts if text]

    def __getattr__(self, name: str) -> Any:
        """Proxy attributes to underlying pipeline.

        Args:
            name: Attribute name

        Returns:
            Attribute from underlying pipeline
        """
        return getattr(self.pipeline, name)

    def __repr__(self) -> str:
        """String representation of RaxePipeline.

        Returns:
            Human-readable string
        """
        model_name = getattr(self.pipeline.model, "name_or_path", "unknown")
        return (
            f"RaxePipeline(task={self.task!r}, model={model_name!r}, "
            f"block_input={self.raxe_block_on_input_threats}, "
            f"block_output={self.raxe_block_on_output_threats})"
        )
