"""Google Vertex AI wrapper with automatic RAXE scanning.

Wrapper for Google Cloud Vertex AI that scans all prompts and responses.

This wrapper provides a convenient interface for using RAXE with Vertex AI
models including PaLM and Gemini.

Usage:
    from raxe.sdk.wrappers import RaxeVertexAI

    # Initialize with Google Cloud project
    client = RaxeVertexAI(
        project="my-project",
        location="us-central1"
    )

    # Generate with automatic scanning
    response = client.generate(
        prompt="What is the capital of France?",
        model="text-bison"
    )
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


class RaxeVertexAI:
    """Vertex AI wrapper with RAXE protection.

    This wrapper provides a simplified interface for using Google Vertex AI
    with automatic RAXE scanning of prompts and responses.

    Supports:
        - PaLM 2 models (text-bison, chat-bison)
        - Gemini models (gemini-pro, gemini-pro-vision)
        - Both generate() and chat() interfaces

    Attributes:
        raxe: Raxe client instance for scanning
        project: Google Cloud project ID
        location: Google Cloud location
        raxe_block_on_threat: Whether to block requests on threat detection
        raxe_scan_responses: Whether to scan model responses

    Example:
        >>> from raxe.sdk.wrappers import RaxeVertexAI
        >>>
        >>> # Initialize
        >>> client = RaxeVertexAI(
        ...     project="my-project",
        ...     location="us-central1"
        ... )
        >>>
        >>> # Generate text
        >>> response = client.generate(
        ...     prompt="Explain quantum computing",
        ...     model="text-bison"
        ... )
        >>>
        >>> # Chat interface
        >>> chat = client.start_chat(model="chat-bison")
        >>> response = chat.send_message("Hello")
    """

    def __init__(
        self,
        project: str,
        location: str = "us-central1",
        *,
        raxe: Raxe | None = None,
        raxe_block_on_threat: bool = True,
        raxe_scan_responses: bool = True,
        credentials: Any | None = None,
    ):
        """Initialize RaxeVertexAI client.

        Args:
            project: Google Cloud project ID
            location: Google Cloud location (default: us-central1)
            raxe: Optional Raxe client (creates default if not provided)
            raxe_block_on_threat: Block requests on threat detection
            raxe_scan_responses: Also scan model responses
            credentials: Optional Google Cloud credentials

        Example:
            # With default settings
            client = RaxeVertexAI(
                project="my-project",
                location="us-central1"
            )

            # With custom Raxe client
            raxe = Raxe(telemetry=False)
            client = RaxeVertexAI(
                project="my-project",
                raxe=raxe
            )

            # Monitoring mode only
            client = RaxeVertexAI(
                project="my-project",
                raxe_block_on_threat=False
            )

        Raises:
            ImportError: If google-cloud-aiplatform package not installed
        """
        # Try to import Vertex AI
        try:
            from google.cloud import aiplatform
        except ImportError as e:
            raise ImportError(
                "google-cloud-aiplatform package is required for RaxeVertexAI. "
                "Install with: pip install google-cloud-aiplatform"
            ) from e

        # Initialize Vertex AI
        aiplatform.init(
            project=project,
            location=location,
            credentials=credentials,
        )

        # Create or use provided Raxe client
        if raxe is None:
            from raxe.sdk.client import Raxe
            raxe = Raxe()

        self.raxe = raxe
        self.project = project
        self.location = location
        self.raxe_block_on_threat = raxe_block_on_threat
        self.raxe_scan_responses = raxe_scan_responses
        self._aiplatform = aiplatform

        logger.debug(
            f"RaxeVertexAI initialized: project={project}, location={location}, "
            f"block={raxe_block_on_threat}, scan_responses={raxe_scan_responses}"
        )

    def generate(
        self,
        prompt: str,
        *,
        model: str = "text-bison",
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        top_p: float = 0.95,
        top_k: int = 40,
        **kwargs
    ) -> str:
        """Generate text with automatic scanning.

        Args:
            prompt: Input prompt to generate from
            model: Model name (text-bison, gemini-pro, etc.)
            temperature: Sampling temperature (0.0-1.0)
            max_output_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            **kwargs: Additional model parameters

        Returns:
            Generated text response

        Raises:
            RaxeBlockedError: If threat detected and blocking enabled

        Example:
            >>> client = RaxeVertexAI(project="my-project")
            >>> response = client.generate(
            ...     prompt="Explain photosynthesis",
            ...     model="text-bison",
            ...     temperature=0.3
            ... )
            >>> print(response)
        """
        # Scan prompt before sending
        self._scan_prompt(prompt)

        # Generate with Vertex AI
        if model.startswith("gemini"):
            response_text = self._generate_gemini(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **kwargs
            )
        else:
            response_text = self._generate_palm(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_p=top_p,
                top_k=top_k,
                **kwargs
            )

        # Scan response
        if self.raxe_scan_responses and response_text:
            self._scan_response(response_text)

        return response_text

    def start_chat(
        self,
        *,
        model: str = "chat-bison",
        context: str | None = None,
        examples: list[dict[str, str]] | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        top_p: float = 0.95,
        top_k: int = 40,
        **kwargs
    ) -> RaxeVertexAIChat:
        """Start a chat session with automatic scanning.

        Args:
            model: Chat model name (chat-bison, gemini-pro, etc.)
            context: Optional conversation context
            examples: Optional example exchanges
            temperature: Sampling temperature (0.0-1.0)
            max_output_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            **kwargs: Additional model parameters

        Returns:
            RaxeVertexAIChat session object

        Example:
            >>> client = RaxeVertexAI(project="my-project")
            >>> chat = client.start_chat(model="chat-bison")
            >>> response = chat.send_message("Hello!")
            >>> print(response)
        """
        return RaxeVertexAIChat(
            parent=self,
            model=model,
            context=context,
            examples=examples,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k,
            **kwargs
        )

    def _generate_palm(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        top_p: float,
        top_k: int,
        **kwargs
    ) -> str:
        """Generate with PaLM models.

        Args:
            prompt: Input prompt
            model: PaLM model name
            temperature: Sampling temperature
            max_output_tokens: Max tokens
            top_p: Nucleus sampling
            top_k: Top-k sampling
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        from vertexai.language_models import TextGenerationModel

        model_instance = TextGenerationModel.from_pretrained(model)

        response = model_instance.predict(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k,
            **kwargs
        )

        return response.text if hasattr(response, "text") else str(response)

    def _generate_gemini(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        **kwargs
    ) -> str:
        """Generate with Gemini models.

        Args:
            prompt: Input prompt
            model: Gemini model name
            temperature: Sampling temperature
            max_output_tokens: Max tokens
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        from vertexai.generative_models import GenerativeModel

        model_instance = GenerativeModel(model)

        response = model_instance.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                **kwargs
            }
        )

        return response.text if hasattr(response, "text") else str(response)

    def _scan_prompt(self, prompt: str):
        """Scan a prompt for threats.

        Args:
            prompt: Prompt to scan

        Raises:
            RaxeBlockedError: If threat detected and blocking enabled
        """
        result = self.raxe.scan(
            prompt,
            block_on_threat=self.raxe_block_on_threat
        )

        if result.has_threats:
            logger.warning(
                f"Threat detected in Vertex AI prompt: {result.severity} "
                f"(block={self.raxe_block_on_threat})"
            )

    def _scan_response(self, response: str):
        """Scan a model response for threats.

        Args:
            response: Response to scan
        """
        try:
            result = self.raxe.scan(response, block_on_threat=False)
            if result.has_threats:
                logger.info(
                    f"Threat detected in Vertex AI response: {result.severity}"
                )
        except Exception as e:
            logger.error(f"Failed to scan response: {e}")

    def __repr__(self) -> str:
        """String representation of RaxeVertexAI client.

        Returns:
            Human-readable string
        """
        return (
            f"RaxeVertexAI(project={self.project!r}, location={self.location!r}, "
            f"block_on_threat={self.raxe_block_on_threat})"
        )


class RaxeVertexAIChat:
    """Chat session for Vertex AI with RAXE protection.

    Manages a multi-turn conversation with automatic scanning of
    all messages in both directions.

    Attributes:
        parent: Parent RaxeVertexAI client
        model: Chat model name
        history: Conversation history

    Example:
        >>> chat = client.start_chat(model="chat-bison")
        >>> response1 = chat.send_message("What is AI?")
        >>> response2 = chat.send_message("How does it work?")
    """

    def __init__(
        self,
        parent: RaxeVertexAI,
        model: str,
        context: str | None,
        examples: list[dict[str, str]] | None,
        temperature: float,
        max_output_tokens: int,
        top_p: float,
        top_k: int,
        **kwargs
    ):
        """Initialize chat session.

        Args:
            parent: Parent RaxeVertexAI client
            model: Chat model name
            context: Optional context
            examples: Optional examples
            temperature: Sampling temperature
            max_output_tokens: Max tokens
            top_p: Nucleus sampling
            top_k: Top-k sampling
            **kwargs: Additional parameters
        """
        self.parent = parent
        self.model = model
        self.history: list[dict[str, str]] = []

        # Initialize appropriate chat model
        if model.startswith("gemini"):
            from vertexai.generative_models import GenerativeModel
            model_instance = GenerativeModel(model)
            self._chat = model_instance.start_chat()
        else:
            from vertexai.language_models import ChatModel
            model_instance = ChatModel.from_pretrained(model)
            self._chat = model_instance.start_chat(
                context=context,
                examples=examples,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_p=top_p,
                top_k=top_k,
                **kwargs
            )

    def send_message(self, message: str) -> str:
        """Send a message in the chat with automatic scanning.

        Args:
            message: User message to send

        Returns:
            Model response text

        Raises:
            RaxeBlockedError: If threat detected and blocking enabled

        Example:
            >>> chat = client.start_chat()
            >>> response = chat.send_message("Hello!")
            >>> print(response)
        """
        # Scan user message
        self.parent._scan_prompt(message)

        # Send to model
        response = self._chat.send_message(message)
        response_text = response.text if hasattr(response, "text") else str(response)

        # Scan response
        if self.parent.raxe_scan_responses and response_text:
            self.parent._scan_response(response_text)

        # Update history
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": response_text})

        return response_text

    def __repr__(self) -> str:
        """String representation of chat session.

        Returns:
            Human-readable string
        """
        return f"RaxeVertexAIChat(model={self.model!r}, messages={len(self.history)})"
