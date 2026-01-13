"""DSPy Integration.

This module provides RAXE integration with DSPy for automatic security
scanning of LLM pipelines and modules.

DSPy is a framework for programming language models through declarative
signatures and automatic optimization. RAXE integrates as a callback
to scan inputs/outputs at various stages of DSPy module execution.

Default behavior is LOG-ONLY (safe to add to production without breaking flows).
Enable blocking with appropriate ScanMode for strict mode.

Usage (Callback Mode):
    import dspy
    from raxe import Raxe
    from raxe.sdk.integrations.dspy import RaxeDSPyCallback

    # Create and register callback
    callback = RaxeDSPyCallback(Raxe())
    dspy.configure(callbacks=[callback])

    # All DSPy module calls are now scanned
    class MyModule(dspy.Module):
        def forward(self, question):
            ...

Usage (Module Wrapper Mode):
    from raxe.sdk.integrations.dspy import RaxeModuleGuard

    # Create guard
    guard = RaxeModuleGuard(Raxe())

    # Wrap module
    protected_module = guard.wrap_module(my_module)

    # Calls are automatically scanned
    result = protected_module(question="What is AI?")

For comprehensive tracing, combine with DSPy's built-in tracing:
    with dspy.settings.trace():
        result = protected_module(question="...")
        history = dspy.settings.trace_history
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    ThreatDetectedError,
    create_agent_scanner,
)

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DSPyConfig:
    """Configuration for DSPy integration.

    Attributes:
        block_on_threats: Whether to raise exception on threat detection.
            Default is False (log-only mode, safe for production).
        scan_module_inputs: Scan inputs to DSPy modules.
        scan_module_outputs: Scan outputs from DSPy modules.
        scan_lm_prompts: Scan prompts sent to language models.
        scan_lm_responses: Scan responses from language models.
        scan_tool_calls: Scan tool/function call arguments.
        scan_tool_results: Scan tool/function results.

    Example:
        # Log-only mode (default)
        config = DSPyConfig()

        # Blocking mode for LM calls
        config = DSPyConfig(
            block_on_threats=True,
            scan_lm_prompts=True,
            scan_lm_responses=True,
        )
    """

    block_on_threats: bool = False
    scan_module_inputs: bool = True
    scan_module_outputs: bool = True
    scan_lm_prompts: bool = True
    scan_lm_responses: bool = True
    scan_tool_calls: bool = True
    scan_tool_results: bool = True


# =============================================================================
# Callback Handler
# =============================================================================


class RaxeDSPyCallback:
    """DSPy callback handler for RAXE security scanning.

    This class implements the DSPy BaseCallback interface to provide
    automatic security scanning at various stages of module execution.

    Attributes:
        raxe: Raxe client for scanning
        config: Integration configuration

    Example:
        import dspy
        from raxe import Raxe
        from raxe.sdk.integrations.dspy import RaxeDSPyCallback

        # Create and register callback
        callback = RaxeDSPyCallback(Raxe())
        dspy.configure(callbacks=[callback])

        # Define and run module
        class QA(dspy.Module):
            def forward(self, question):
                return dspy.ChainOfThought("question -> answer")(question=question)

        result = QA()(question="What is AI?")
    """

    def __init__(
        self,
        raxe: Raxe | None = None,
        config: DSPyConfig | None = None,
    ) -> None:
        """Initialize DSPy callback handler.

        Args:
            raxe: Raxe client for scanning. Created if not provided.
            config: Integration configuration. Uses defaults if not provided.
        """
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe
        self.config = config or DSPyConfig()

        # Create AgentScanner for unified scanning with integration telemetry
        scanner_config = AgentScannerConfig(
            scan_prompts=True,
            scan_responses=True,
            on_threat="block" if self.config.block_on_threats else "log",
        )
        self._scanner = create_agent_scanner(raxe, scanner_config, integration_type="dspy")

        # Statistics
        self._stats = {
            "module_calls": 0,
            "lm_calls": 0,
            "tool_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

        logger.debug(f"RaxeDSPyCallback initialized: block={self.config.block_on_threats}")

    def on_module_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when a DSPy Module starts execution.

        Args:
            call_id: Unique identifier for this call
            instance: Module instance
            inputs: Input arguments to the module
        """
        self._stats["module_calls"] += 1

        if not self.config.scan_module_inputs:
            return

        try:
            # Extract and scan text from inputs
            for key, value in inputs.items():
                text = self._extract_text(value)
                if text and text.strip():
                    self._scan_text(
                        text,
                        scan_type="prompt",
                        context_source="module_input",
                        context_key=key,
                        call_id=call_id,
                    )
        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_module_input_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_module_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when a DSPy Module completes execution.

        Args:
            call_id: Unique identifier for this call
            outputs: Output from the module
            exception: Exception if module failed
        """
        if exception is not None or not self.config.scan_module_outputs:
            return

        try:
            # Extract and scan text from outputs
            if hasattr(outputs, "__dict__"):
                for key, value in vars(outputs).items():
                    if not key.startswith("_"):
                        text = self._extract_text(value)
                        if text and text.strip():
                            self._scan_text(
                                text,
                                scan_type="response",
                                context_source="module_output",
                                context_key=key,
                                call_id=call_id,
                            )
            else:
                text = self._extract_text(outputs)
                if text and text.strip():
                    self._scan_text(
                        text,
                        scan_type="response",
                        context_source="module_output",
                        call_id=call_id,
                    )
        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_module_output_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_lm_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when a DSPy LM (language model) call starts.

        Args:
            call_id: Unique identifier for this call
            instance: LM instance
            inputs: Input to the LM (prompt, messages, etc.)
        """
        self._stats["lm_calls"] += 1

        if not self.config.scan_lm_prompts:
            return

        try:
            # Extract prompt text
            prompt = inputs.get("prompt", "")
            messages = inputs.get("messages", [])

            if prompt and isinstance(prompt, str) and prompt.strip():
                self._scan_text(
                    prompt,
                    scan_type="prompt",
                    context_source="lm_prompt",
                    call_id=call_id,
                )

            if messages:
                for msg in messages:
                    if isinstance(msg, dict):
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user" and content:
                            text = self._extract_text(content)
                            if text and text.strip():
                                self._scan_text(
                                    text,
                                    scan_type="prompt",
                                    context_source="lm_message",
                                    call_id=call_id,
                                )

        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_lm_prompt_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_lm_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when a DSPy LM call completes.

        Args:
            call_id: Unique identifier for this call
            outputs: LM response
            exception: Exception if LM call failed
        """
        if exception is not None or not self.config.scan_lm_responses:
            return

        try:
            # Extract response text
            text = self._extract_text(outputs)
            if text and text.strip():
                self._scan_text(
                    text,
                    scan_type="response",
                    context_source="lm_response",
                    call_id=call_id,
                )
        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_lm_response_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_tool_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when a DSPy Tool call starts.

        Args:
            call_id: Unique identifier for this call
            instance: Tool instance
            inputs: Tool input arguments
        """
        self._stats["tool_calls"] += 1

        if not self.config.scan_tool_calls:
            return

        try:
            # Scan tool arguments
            for key, value in inputs.items():
                text = self._extract_text(value)
                if text and text.strip():
                    self._scan_text(
                        text,
                        scan_type="prompt",
                        context_source="tool_input",
                        context_key=key,
                        call_id=call_id,
                    )
        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_tool_input_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_tool_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when a DSPy Tool call completes.

        Args:
            call_id: Unique identifier for this call
            outputs: Tool output
            exception: Exception if tool failed
        """
        if exception is not None or not self.config.scan_tool_results:
            return

        try:
            text = self._extract_text(outputs)
            if text and text.strip():
                self._scan_text(
                    text,
                    scan_type="response",
                    context_source="tool_output",
                    call_id=call_id,
                )
        except ThreatDetectedError:
            raise
        except Exception as e:
            logger.error(
                "dspy_tool_output_scan_error",
                extra={"error": str(e), "call_id": call_id},
            )

    def on_adapter_format_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when adapter starts formatting prompt."""
        pass  # Not scanning adapter formatting

    def on_adapter_format_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when adapter finishes formatting prompt."""
        pass  # Not scanning adapter formatting

    def on_adapter_parse_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when adapter starts parsing output."""
        pass  # Not scanning adapter parsing

    def on_adapter_parse_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when adapter finishes parsing output."""
        pass  # Not scanning adapter parsing

    def on_evaluate_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Called when evaluation starts."""
        pass  # Not scanning evaluation

    def on_evaluate_end(
        self,
        call_id: str,
        outputs: Any,
        exception: Exception | None,
    ) -> None:
        """Called when evaluation ends."""
        pass  # Not scanning evaluation

    def _scan_text(
        self,
        text: str,
        scan_type: str,
        context_source: str,
        context_key: str | None = None,
        call_id: str | None = None,
    ) -> None:
        """Scan text for threats.

        Args:
            text: Text to scan
            scan_type: "prompt" or "response"
            context_source: Source of the text (module_input, lm_prompt, etc.)
            context_key: Optional key/field name
            call_id: Optional call identifier

        Raises:
            ThreatDetectedError: If blocking is enabled and threat detected
        """
        if scan_type == "prompt":
            result = self._scanner.scan_prompt(text)
        else:
            result = self._scanner.scan_response(text)

        if result.has_threats:
            self._stats["threats_detected"] += 1
            logger.warning(
                "dspy_threat_detected",
                extra={
                    "source": context_source,
                    "key": context_key,
                    "severity": result.severity,
                    "rule_ids": result.rule_ids,
                    "call_id": call_id,
                },
            )

            if result.should_block:
                self._stats["threats_blocked"] += 1
                raise ThreatDetectedError(result)

    def _extract_text(self, value: Any) -> str:
        """Extract text from various value types.

        Args:
            value: Value to extract text from

        Returns:
            Extracted text string
        """
        if isinstance(value, str):
            return value

        if isinstance(value, list):
            texts = []
            for item in value:
                text = self._extract_text(item)
                if text:
                    texts.append(text)
            return " ".join(texts)

        if isinstance(value, dict):
            # Handle message dict
            if "content" in value:
                return self._extract_text(value["content"])
            if "text" in value:
                return value["text"]

        # Try to convert to string
        if value is not None:
            try:
                return str(value)
            except Exception:
                pass

        return ""

    @property
    def stats(self) -> dict[str, int]:
        """Get callback statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "module_calls": 0,
            "lm_calls": 0,
            "tool_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RaxeDSPyCallback(block_on_threats={self.config.block_on_threats}, "
            f"scan_lm_prompts={self.config.scan_lm_prompts})"
        )


# =============================================================================
# Module Guard Wrapper
# =============================================================================


class RaxeModuleGuard:
    """Guard wrapper for DSPy modules.

    Wraps a DSPy module to automatically scan inputs and outputs.
    Useful when you can't or don't want to use global callbacks.

    Attributes:
        raxe: Raxe client for scanning
        config: Guard configuration

    Example:
        from raxe import Raxe
        from raxe.sdk.integrations.dspy import RaxeModuleGuard

        guard = RaxeModuleGuard(Raxe())

        # Wrap module
        protected = guard.wrap_module(my_module)

        # Use protected module
        result = protected(question="What is AI?")
    """

    def __init__(
        self,
        raxe: Raxe | None = None,
        config: DSPyConfig | None = None,
    ) -> None:
        """Initialize module guard.

        Args:
            raxe: Raxe client for scanning. Created if not provided.
            config: Guard configuration. Uses defaults if not provided.
        """
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe
        self.config = config or DSPyConfig()

        # Create AgentScanner
        scanner_config = AgentScannerConfig(
            scan_prompts=True,
            scan_responses=True,
            on_threat="block" if self.config.block_on_threats else "log",
        )
        self._scanner = create_agent_scanner(raxe, scanner_config, integration_type="dspy")

        # Statistics
        self._stats = {
            "total_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

    def wrap_module(self, module: T) -> T:
        """Wrap a DSPy module with RAXE scanning.

        Args:
            module: DSPy module to wrap

        Returns:
            Wrapped module with scanning enabled
        """
        return _ModuleWrapper(module, self)  # type: ignore

    def scan_inputs(self, inputs: dict[str, Any]) -> None:
        """Scan module inputs for threats.

        Args:
            inputs: Input arguments

        Raises:
            ThreatDetectedError: If blocking and threat detected
        """
        self._stats["total_calls"] += 1

        if not self.config.scan_module_inputs:
            return

        for key, value in inputs.items():
            text = self._extract_text(value)
            if text and text.strip():
                result = self._scanner.scan_prompt(text)

                if result.has_threats:
                    self._stats["threats_detected"] += 1
                    logger.warning(
                        "dspy_guard_input_threat",
                        extra={
                            "key": key,
                            "severity": result.severity,
                            "rule_ids": result.rule_ids,
                        },
                    )

                    if result.should_block:
                        self._stats["threats_blocked"] += 1
                        raise ThreatDetectedError(result)

    def scan_outputs(self, outputs: Any) -> None:
        """Scan module outputs for threats.

        Args:
            outputs: Module outputs
        """
        if not self.config.scan_module_outputs:
            return

        if hasattr(outputs, "__dict__"):
            for key, value in vars(outputs).items():
                if not key.startswith("_"):
                    text = self._extract_text(value)
                    if text and text.strip():
                        result = self._scanner.scan_response(text)

                        if result.has_threats:
                            self._stats["threats_detected"] += 1
                            logger.warning(
                                "dspy_guard_output_threat",
                                extra={
                                    "key": key,
                                    "severity": result.severity,
                                    "rule_ids": result.rule_ids,
                                },
                            )
        else:
            text = self._extract_text(outputs)
            if text and text.strip():
                result = self._scanner.scan_response(text)

                if result.has_threats:
                    self._stats["threats_detected"] += 1
                    logger.warning(
                        "dspy_guard_output_threat",
                        extra={
                            "severity": result.severity,
                            "rule_ids": result.rule_ids,
                        },
                    )

    def _extract_text(self, value: Any) -> str:
        """Extract text from value."""
        if isinstance(value, str):
            return value

        if isinstance(value, list):
            texts = [self._extract_text(v) for v in value]
            return " ".join(filter(None, texts))

        if value is not None:
            try:
                return str(value)
            except Exception:
                pass

        return ""

    @property
    def stats(self) -> dict[str, int]:
        """Get guard statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_calls": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }


class _ModuleWrapper:
    """Internal wrapper for DSPy modules."""

    def __init__(self, module: Any, guard: RaxeModuleGuard) -> None:
        self._module = module
        self._guard = guard

    def __call__(self, **kwargs: Any) -> Any:
        """Execute wrapped module with scanning."""
        # Scan inputs
        self._guard.scan_inputs(kwargs)

        # Execute module
        result = self._module(**kwargs)

        # Scan outputs
        self._guard.scan_outputs(result)

        return result

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to wrapped module."""
        return getattr(self._module, name)


# =============================================================================
# Convenience Factory Functions
# =============================================================================


def create_dspy_callback(
    raxe: Raxe | None = None,
    *,
    block_on_threats: bool = False,
    scan_lm_prompts: bool = True,
    scan_lm_responses: bool = True,
) -> RaxeDSPyCallback:
    """Create a DSPy callback handler.

    Factory function for creating a configured callback handler.

    Args:
        raxe: Raxe client. Created if not provided.
        block_on_threats: Whether to block on threat detection.
        scan_lm_prompts: Whether to scan LM prompts.
        scan_lm_responses: Whether to scan LM responses.

    Returns:
        Configured RaxeDSPyCallback

    Example:
        import dspy
        from raxe.sdk.integrations.dspy import create_dspy_callback

        callback = create_dspy_callback(block_on_threats=True)
        dspy.configure(callbacks=[callback])
    """
    config = DSPyConfig(
        block_on_threats=block_on_threats,
        scan_lm_prompts=scan_lm_prompts,
        scan_lm_responses=scan_lm_responses,
    )
    return RaxeDSPyCallback(raxe, config)


def create_module_guard(
    raxe: Raxe | None = None,
    *,
    block_on_threats: bool = False,
) -> RaxeModuleGuard:
    """Create a DSPy module guard.

    Factory function for creating a module guard.

    Args:
        raxe: Raxe client. Created if not provided.
        block_on_threats: Whether to block on threat detection.

    Returns:
        Configured RaxeModuleGuard

    Example:
        from raxe.sdk.integrations.dspy import create_module_guard

        guard = create_module_guard(block_on_threats=True)
        protected = guard.wrap_module(my_module)
    """
    config = DSPyConfig(block_on_threats=block_on_threats)
    return RaxeModuleGuard(raxe, config)
