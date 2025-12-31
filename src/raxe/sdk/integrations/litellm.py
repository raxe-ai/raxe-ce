"""LiteLLM Integration.

This module provides RAXE integration with LiteLLM for automatic security
scanning of LLM API calls across 200+ providers.

LiteLLM is a unified interface for calling OpenAI, Anthropic, Azure, Hugging Face,
Replicate and more. RAXE integrates as a custom callback to scan inputs/outputs.

Default behavior is LOG-ONLY (safe to add to production without breaking flows).
Enable blocking with appropriate ScanMode for strict mode.

Usage (Callback Mode):
    import litellm
    from raxe import Raxe
    from raxe.sdk.integrations.litellm import RaxeLiteLLMCallback

    # Create callback handler
    callback = RaxeLiteLLMCallback(Raxe())

    # Register with LiteLLM
    litellm.callbacks = [callback]

    # All LLM calls now scanned
    response = litellm.completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )

Usage (Wrapper Mode):
    from raxe.sdk.integrations.litellm import create_litellm_handler

    handler = create_litellm_handler(
        block_on_threats=True,
        scan_responses=True,
    )
    litellm.callbacks = [handler]

For Proxy Configuration:
    Add RAXE as a custom callback in config.yaml:
    ```yaml
    litellm_settings:
      callbacks: ["path/to/raxe_callback.py"]
    ```
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    MessageType,
    ScanContext,
    ThreatDetectedError,
    create_agent_scanner,
)
from raxe.sdk.exceptions import SecurityException

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class LiteLLMConfig:
    """Configuration for LiteLLM integration.

    Attributes:
        block_on_threats: Whether to raise exception on threat detection.
            Default is False (log-only mode, safe for production).
        scan_inputs: Scan input messages before sending to LLM.
        scan_outputs: Scan LLM responses for threats.
        include_metadata: Include LiteLLM metadata in scan context.

    Example:
        # Log-only mode (default)
        config = LiteLLMConfig()

        # Blocking mode
        config = LiteLLMConfig(
            block_on_threats=True,
            scan_inputs=True,
            scan_outputs=True,
        )
    """

    block_on_threats: bool = False
    scan_inputs: bool = True
    scan_outputs: bool = True
    include_metadata: bool = True


# =============================================================================
# Callback Handler
# =============================================================================


class RaxeLiteLLMCallback:
    """LiteLLM callback handler for RAXE security scanning.

    This class implements the LiteLLM CustomLogger interface to provide
    automatic security scanning of all LLM API calls.

    Attributes:
        raxe: Raxe client for scanning
        config: Integration configuration

    Example:
        import litellm
        from raxe import Raxe
        from raxe.sdk.integrations.litellm import RaxeLiteLLMCallback

        # Create callback
        callback = RaxeLiteLLMCallback(Raxe())
        litellm.callbacks = [callback]

        # Make API call - automatically scanned
        response = litellm.completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """

    def __init__(
        self,
        raxe: "Raxe | None" = None,
        config: LiteLLMConfig | None = None,
    ) -> None:
        """Initialize LiteLLM callback handler.

        Args:
            raxe: Raxe client for scanning. Created if not provided.
            config: Integration configuration. Uses defaults if not provided.
        """
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe
        self.config = config or LiteLLMConfig()

        # Create AgentScanner for unified scanning with integration telemetry
        scanner_config = AgentScannerConfig(
            scan_prompts=self.config.scan_inputs,
            scan_responses=self.config.scan_outputs,
            on_threat="block" if self.config.block_on_threats else "log",
        )
        self._scanner = create_agent_scanner(raxe, scanner_config, integration_type="litellm")

        # Statistics
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

        logger.debug(
            f"RaxeLiteLLMCallback initialized: block={self.config.block_on_threats}, "
            f"scan_inputs={self.config.scan_inputs}, scan_outputs={self.config.scan_outputs}"
        )

    def log_pre_api_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> None:
        """Called before API call is made.

        Scans input messages for threats before sending to LLM.

        Args:
            model: Model being called
            messages: Input messages
            kwargs: Additional API call arguments
        """
        self._stats["total_calls"] += 1

        if not self.config.scan_inputs:
            return

        try:
            # Extract and scan user messages
            for message in messages:
                if isinstance(message, dict):
                    role = message.get("role", "")
                    content = message.get("content", "")

                    if role == "user" and content:
                        text = self._extract_text(content)
                        if text.strip():
                            context = ScanContext(
                                message_type=MessageType.HUMAN_INPUT,
                                metadata={
                                    "source": "litellm",
                                    "model": model,
                                    "hook": "pre_api_call",
                                },
                            )

                            result = self._scanner.scan_prompt(text)

                            if result.has_threats:
                                self._stats["threats_detected"] += 1
                                logger.warning(
                                    "litellm_input_threat",
                                    extra={
                                        "model": model,
                                        "severity": result.severity,
                                        "rule_ids": result.rule_ids,
                                    },
                                )

                                if result.should_block:
                                    self._stats["threats_blocked"] += 1
                                    raise ThreatDetectedError(result)

        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "litellm_pre_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    def log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Called after successful API call.

        Scans LLM response for threats.

        Args:
            kwargs: API call details (model, messages, etc.)
            response_obj: LLM response object
            start_time: Call start time
            end_time: Call end time
        """
        self._stats["successful_calls"] += 1

        if not self.config.scan_outputs:
            return

        try:
            # Extract response text
            response_text = self._extract_response_text(response_obj)

            if response_text and response_text.strip():
                model = kwargs.get("model", "unknown")

                result = self._scanner.scan_response(response_text)

                if result.has_threats:
                    self._stats["threats_detected"] += 1
                    logger.warning(
                        "litellm_output_threat",
                        extra={
                            "model": model,
                            "severity": result.severity,
                            "rule_ids": result.rule_ids,
                        },
                    )

                    # Note: For output scanning, we log but don't block
                    # as the response has already been generated

        except Exception as e:
            logger.error(
                "litellm_success_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    def log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Called after failed API call.

        Logs the failure for monitoring.

        Args:
            kwargs: API call details
            response_obj: Error/exception object
            start_time: Call start time
            end_time: Call end time
        """
        self._stats["failed_calls"] += 1

        logger.debug(
            "litellm_call_failed",
            extra={
                "model": kwargs.get("model", "unknown"),
                "error": str(response_obj),
            },
        )

    async def async_log_pre_api_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> None:
        """Async version of log_pre_api_call."""
        # Delegate to sync version (RAXE scanning is CPU-bound)
        self.log_pre_api_call(model, messages, kwargs)

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Async version of log_success_event."""
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Async version of log_failure_event."""
        self.log_failure_event(kwargs, response_obj, start_time, end_time)

    def _extract_text(self, content: Any) -> str:
        """Extract text from message content.

        Args:
            content: Content in various formats

        Returns:
            Extracted text string
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            # Multi-modal content
            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(part.get("text", ""))
                elif isinstance(part, str):
                    texts.append(part)
            return " ".join(texts)

        return ""

    def _extract_response_text(self, response_obj: Any) -> str:
        """Extract text from LiteLLM response.

        Args:
            response_obj: LiteLLM response object

        Returns:
            Extracted response text
        """
        try:
            # Standard OpenAI-style response
            if hasattr(response_obj, "choices"):
                texts = []
                for choice in response_obj.choices:
                    if hasattr(choice, "message") and hasattr(choice.message, "content"):
                        if choice.message.content:
                            texts.append(choice.message.content)
                    elif hasattr(choice, "text"):
                        if choice.text:
                            texts.append(choice.text)
                return " ".join(texts)

            # Dict response
            if isinstance(response_obj, dict):
                choices = response_obj.get("choices", [])
                texts = []
                for choice in choices:
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        content = message.get("content", "")
                        if content:
                            texts.append(content)
                return " ".join(texts)

        except Exception as e:
            logger.debug(f"Failed to extract response text: {e}")

        return ""

    @property
    def stats(self) -> dict[str, int]:
        """Get callback statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RaxeLiteLLMCallback(block_on_threats={self.config.block_on_threats}, "
            f"scan_inputs={self.config.scan_inputs}, "
            f"scan_outputs={self.config.scan_outputs})"
        )


# =============================================================================
# Convenience Factory Function
# =============================================================================


def create_litellm_handler(
    raxe: "Raxe | None" = None,
    *,
    block_on_threats: bool = False,
    scan_inputs: bool = True,
    scan_outputs: bool = True,
) -> RaxeLiteLLMCallback:
    """Create a LiteLLM callback handler.

    Factory function for creating a configured callback handler.

    Args:
        raxe: Raxe client. Created if not provided.
        block_on_threats: Whether to block on threat detection.
        scan_inputs: Whether to scan input messages.
        scan_outputs: Whether to scan LLM responses.

    Returns:
        Configured RaxeLiteLLMCallback

    Example:
        import litellm
        from raxe.sdk.integrations.litellm import create_litellm_handler

        handler = create_litellm_handler(block_on_threats=True)
        litellm.callbacks = [handler]
    """
    config = LiteLLMConfig(
        block_on_threats=block_on_threats,
        scan_inputs=scan_inputs,
        scan_outputs=scan_outputs,
    )
    return RaxeLiteLLMCallback(raxe, config)
