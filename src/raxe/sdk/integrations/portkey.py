"""Portkey AI Gateway Integration.

This module provides RAXE integration with Portkey AI Gateway for:
1. Webhook-based guardrails (RAXE as a Portkey custom guardrail)
2. Client-side scanning (wrapping Portkey SDK calls)

Portkey is an AI gateway that routes requests to 200+ LLMs with built-in
guardrails, caching, and observability. RAXE can integrate as:

- **Webhook Guardrail**: Portkey calls RAXE endpoint for input/output scanning
- **Client Wrapper**: RAXE scans locally before/after Portkey calls

Usage (Webhook):
    from raxe.sdk.integrations.portkey import RaxePortkeyWebhook

    # Create webhook handler
    webhook = RaxePortkeyWebhook()

    # FastAPI integration
    @app.post("/raxe/guardrail")
    async def guardrail(request: Request):
        data = await request.json()
        return webhook.handle_request(data)

Usage (Client Wrapper):
    from portkey_ai import Portkey
    from raxe.sdk.integrations.portkey import RaxePortkeyGuard

    # Create guard
    guard = RaxePortkeyGuard(block_on_threats=True)

    # Wrap Portkey client
    client = guard.wrap_client(Portkey(api_key="..."))

    # Calls are automatically scanned
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4"
    )

For Portkey configuration, add RAXE as a webhook guardrail:
    {
        "beforeRequestHooks": [{
            "id": "raxe-guardrail",
            "type": "guardrail",
            "checks": [{
                "id": "default.webhook",
                "parameters": {
                    "webhookURL": "https://your-endpoint/raxe/guardrail",
                    "headers": {"Authorization": "Bearer YOUR_KEY"}
                }
            }],
            "deny": true
        }]
    }
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from raxe.sdk.exceptions import SecurityException

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class PortkeyGuardConfig:
    """Configuration for Portkey guardrail integration.

    Attributes:
        block_on_threats: Whether to block (return false verdict) on threats.
            Default is False (log-only mode, always returns true verdict).
        block_severity_threshold: Minimum severity to trigger blocking.
            Options: "LOW", "MEDIUM", "HIGH", "CRITICAL"
        scan_inputs: Scan input messages (beforeRequest)
        scan_outputs: Scan output responses (afterRequest)
        include_scan_details: Include detailed scan info in response data
        fail_open: Return true verdict on errors (Portkey default behavior)

    Example:
        # Log-only mode (default)
        config = PortkeyGuardConfig()

        # Blocking mode
        config = PortkeyGuardConfig(
            block_on_threats=True,
            block_severity_threshold="HIGH",
        )
    """

    block_on_threats: bool = False
    block_severity_threshold: str = "HIGH"
    scan_inputs: bool = True
    scan_outputs: bool = True
    include_scan_details: bool = True
    fail_open: bool = True  # Match Portkey's timeout behavior


# =============================================================================
# Webhook Handler
# =============================================================================


class RaxePortkeyWebhook:
    """Webhook handler for Portkey guardrail integration.

    Handles incoming guardrail requests from Portkey and returns
    verdicts in Portkey's expected format.

    Portkey sends requests with:
        - eventType: "beforeRequest" or "afterRequest"
        - request: The LLM request (for beforeRequest)
        - response: The LLM response (for afterRequest)
        - metadata: Optional metadata from x-portkey-metadata header

    RAXE returns:
        - verdict: true (pass) or false (fail/block)
        - data: Scan details including reason, severity, detections

    Attributes:
        raxe: Raxe client for scanning
        config: Guardrail configuration

    Example:
        webhook = RaxePortkeyWebhook()

        # Handle incoming request
        result = webhook.handle_request({
            "request": {"messages": [...]},
            "eventType": "beforeRequest"
        })
        # Returns: {"verdict": true, "data": {...}}
    """

    def __init__(
        self,
        raxe: "Raxe | None" = None,
        config: PortkeyGuardConfig | None = None,
    ) -> None:
        """Initialize webhook handler.

        Args:
            raxe: Raxe client for scanning. Created if not provided.
            config: Guardrail configuration. Uses defaults if not provided.
        """
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe
        self.config = config or PortkeyGuardConfig()

        # Statistics
        self._stats = {
            "total_requests": 0,
            "before_requests": 0,
            "after_requests": 0,
            "threats_detected": 0,
            "verdicts_false": 0,
            "errors": 0,
        }

    def handle_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incoming Portkey guardrail request.

        Args:
            data: Request data from Portkey containing:
                - eventType: "beforeRequest" or "afterRequest"
                - request: LLM request (for beforeRequest)
                - response: LLM response (for afterRequest)
                - metadata: Optional metadata

        Returns:
            Portkey-compatible verdict response:
                {
                    "verdict": true/false,
                    "data": {
                        "reason": "...",
                        "severity": "...",
                        "detections": 0,
                        "rule_ids": [...],
                        "scan_duration_ms": 5.2
                    }
                }
        """
        self._stats["total_requests"] += 1
        start_time = time.time()

        try:
            event_type = data.get("eventType", "beforeRequest")

            if event_type == "beforeRequest":
                self._stats["before_requests"] += 1
                return self._handle_before_request(data, start_time)
            elif event_type == "afterRequest":
                self._stats["after_requests"] += 1
                return self._handle_after_request(data, start_time)
            else:
                # Unknown event type, pass through
                return self._make_pass_verdict(
                    reason=f"Unknown event type: {event_type}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            self._stats["errors"] += 1
            logger.warning(f"Portkey guardrail error: {e}")

            # Fail-open: return pass verdict on error
            if self.config.fail_open:
                return self._make_pass_verdict(
                    reason="Scan error (fail-open)",
                    duration_ms=(time.time() - start_time) * 1000,
                    error=str(e),
                )
            else:
                return self._make_fail_verdict(
                    reason=f"Scan error: {e}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

    async def handle_request_async(self, data: dict[str, Any]) -> dict[str, Any]:
        """Async version of handle_request.

        Args:
            data: Request data from Portkey

        Returns:
            Portkey-compatible verdict response
        """
        # For now, delegate to sync version
        # Future: implement true async scanning
        return self.handle_request(data)

    def _handle_before_request(
        self,
        data: dict[str, Any],
        start_time: float,
    ) -> dict[str, Any]:
        """Handle beforeRequest event (input scanning).

        Args:
            data: Request data
            start_time: Request start timestamp

        Returns:
            Verdict response
        """
        if not self.config.scan_inputs:
            return self._make_pass_verdict(
                reason="Input scanning disabled",
                duration_ms=(time.time() - start_time) * 1000,
            )

        request = data.get("request", {})
        messages = request.get("messages", [])

        if not messages:
            return self._make_pass_verdict(
                reason="No messages to scan",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Extract text to scan
        text_to_scan = self._extract_messages_text(messages)

        if not text_to_scan.strip():
            return self._make_pass_verdict(
                reason="No text content to scan",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Perform scan
        result = self.raxe.scan(text_to_scan)
        duration_ms = (time.time() - start_time) * 1000

        return self._result_to_verdict(result, duration_ms)

    def _handle_after_request(
        self,
        data: dict[str, Any],
        start_time: float,
    ) -> dict[str, Any]:
        """Handle afterRequest event (output scanning).

        Args:
            data: Response data
            start_time: Request start timestamp

        Returns:
            Verdict response
        """
        if not self.config.scan_outputs:
            return self._make_pass_verdict(
                reason="Output scanning disabled",
                duration_ms=(time.time() - start_time) * 1000,
            )

        response = data.get("response", {})

        # Extract text from response
        text_to_scan = self._extract_response_text(response)

        if not text_to_scan.strip():
            return self._make_pass_verdict(
                reason="No response content to scan",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Perform scan
        result = self.raxe.scan(text_to_scan)
        duration_ms = (time.time() - start_time) * 1000

        return self._result_to_verdict(result, duration_ms)

    def _extract_messages_text(self, messages: list[dict[str, Any]]) -> str:
        """Extract scannable text from messages.

        Focuses on user messages as primary scan targets.

        Args:
            messages: List of chat messages

        Returns:
            Combined text for scanning
        """
        texts = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Scan user messages primarily
            if role == "user" and content:
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    # Multi-modal content
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            texts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            texts.append(part)

        return "\n".join(texts)

    def _extract_response_text(self, response: dict[str, Any]) -> str:
        """Extract scannable text from LLM response.

        Args:
            response: LLM response object

        Returns:
            Combined response text for scanning
        """
        texts = []

        choices = response.get("choices", [])
        for choice in choices:
            message = choice.get("message", {})
            content = message.get("content", "")

            if content:
                texts.append(content)

        return "\n".join(texts)

    def _result_to_verdict(
        self,
        result: Any,
        duration_ms: float,
    ) -> dict[str, Any]:
        """Convert scan result to Portkey verdict format.

        Args:
            result: RAXE scan result
            duration_ms: Scan duration in milliseconds

        Returns:
            Portkey verdict response
        """
        if result.has_threats:
            self._stats["threats_detected"] += 1

            # Determine if we should block based on severity
            should_block = self.config.block_on_threats and self._should_block(result)

            if should_block:
                self._stats["verdicts_false"] += 1
                return self._make_fail_verdict(
                    reason="Threat detected",
                    severity=result.severity,
                    detections=result.total_detections,
                    rule_ids=[d.rule_id for d in result.detections],
                    duration_ms=duration_ms,
                )

        # Pass verdict
        return self._make_pass_verdict(
            reason="No threats detected" if not result.has_threats else "Threat logged (non-blocking)",
            severity=result.severity if result.has_threats else None,
            detections=result.total_detections,
            duration_ms=duration_ms,
        )

    def _should_block(self, result: Any) -> bool:
        """Check if result severity meets blocking threshold.

        Args:
            result: Scan result with severity

        Returns:
            True if should block
        """
        severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        threshold = self.config.block_severity_threshold

        if not result.severity:
            return False

        try:
            result_idx = severity_order.index(result.severity.upper())
            threshold_idx = severity_order.index(threshold.upper())
            return result_idx >= threshold_idx
        except ValueError:
            return False

    def _make_pass_verdict(
        self,
        reason: str,
        duration_ms: float,
        severity: str | None = None,
        detections: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Create a pass (true) verdict response.

        Args:
            reason: Reason for the verdict
            duration_ms: Scan duration
            severity: Detected severity (if any)
            detections: Number of detections
            error: Error message (if any)

        Returns:
            Portkey verdict with verdict=true
        """
        data: dict[str, Any] = {
            "reason": reason,
            "detections": detections,
            "scan_duration_ms": round(duration_ms, 2),
        }

        if severity:
            data["severity"] = severity

        if error:
            data["error"] = error

        return {"verdict": True, "data": data}

    def _make_fail_verdict(
        self,
        reason: str,
        duration_ms: float,
        severity: str | None = None,
        detections: int = 0,
        rule_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a fail (false) verdict response.

        Args:
            reason: Reason for the verdict
            duration_ms: Scan duration
            severity: Detected severity
            detections: Number of detections
            rule_ids: List of triggered rule IDs

        Returns:
            Portkey verdict with verdict=false
        """
        data: dict[str, Any] = {
            "reason": reason,
            "detections": detections,
            "scan_duration_ms": round(duration_ms, 2),
        }

        if severity:
            data["severity"] = severity

        if rule_ids:
            data["rule_ids"] = rule_ids

        return {"verdict": False, "data": data}

    @property
    def stats(self) -> dict[str, int]:
        """Get webhook statistics."""
        return self._stats.copy()


# =============================================================================
# Client Guard
# =============================================================================


class RaxePortkeyGuard:
    """Client-side guard for Portkey SDK.

    Wraps Portkey client to scan inputs before sending and
    optionally scan outputs after receiving.

    Attributes:
        raxe: Raxe client for scanning
        config: Guard configuration

    Example:
        from portkey_ai import Portkey
        from raxe.sdk.integrations.portkey import RaxePortkeyGuard

        guard = RaxePortkeyGuard(block_on_threats=True)
        client = guard.wrap_client(Portkey(api_key="..."))

        # All calls are now scanned
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4"
        )
    """

    def __init__(
        self,
        raxe: "Raxe | None" = None,
        config: PortkeyGuardConfig | None = None,
        *,
        block_on_threats: bool | None = None,
        block_severity_threshold: str | None = None,
    ) -> None:
        """Initialize client guard.

        Args:
            raxe: Raxe client for scanning. Created if not provided.
            config: Guard configuration. Uses defaults if not provided.
            block_on_threats: Override config block_on_threats
            block_severity_threshold: Override config threshold
        """
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe

        # Build config
        if config is None:
            config = PortkeyGuardConfig()

        if block_on_threats is not None:
            config = PortkeyGuardConfig(
                block_on_threats=block_on_threats,
                block_severity_threshold=config.block_severity_threshold,
                scan_inputs=config.scan_inputs,
                scan_outputs=config.scan_outputs,
            )

        if block_severity_threshold is not None:
            config = PortkeyGuardConfig(
                block_on_threats=config.block_on_threats,
                block_severity_threshold=block_severity_threshold,
                scan_inputs=config.scan_inputs,
                scan_outputs=config.scan_outputs,
            )

        self.config = config

        # Statistics
        self._stats = {
            "total_scans": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }

    def wrap_client(self, client: T) -> T:
        """Wrap a Portkey client with RAXE scanning.

        Args:
            client: Portkey client instance

        Returns:
            Wrapped client with scanning enabled
        """
        return _PortkeyClientWrapper(client, self)  # type: ignore

    def scan_and_call(
        self,
        fn: Callable[..., T],
        *,
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> T:
        """Scan input and call function if safe.

        Args:
            fn: Function to call (e.g., client.chat.completions.create)
            messages: Messages to scan
            **kwargs: Additional arguments to pass to fn

        Returns:
            Result from fn

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        self._stats["total_scans"] += 1

        if messages and self.config.scan_inputs:
            # Extract and scan text
            text_to_scan = self._extract_messages_text(messages)

            if text_to_scan.strip():
                result = self.raxe.scan(text_to_scan)

                if result.has_threats:
                    self._stats["threats_detected"] += 1

                    if self.config.block_on_threats and self._should_block(result):
                        self._stats["threats_blocked"] += 1
                        raise SecurityException(result)

        # Call the function
        return fn(messages=messages, **kwargs)

    def _extract_messages_text(self, messages: list[dict[str, Any]]) -> str:
        """Extract scannable text from messages."""
        texts = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and content:
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            texts.append(part.get("text", ""))

        return "\n".join(texts)

    def _should_block(self, result: Any) -> bool:
        """Check if result severity meets blocking threshold."""
        severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        threshold = self.config.block_severity_threshold

        if not result.severity:
            return False

        try:
            result_idx = severity_order.index(result.severity.upper())
            threshold_idx = severity_order.index(threshold.upper())
            return result_idx >= threshold_idx
        except ValueError:
            return False

    @property
    def stats(self) -> dict[str, int]:
        """Get guard statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_scans": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
        }


class _PortkeyClientWrapper:
    """Internal wrapper for Portkey client.

    Intercepts chat.completions.create calls for scanning.
    """

    def __init__(self, client: Any, guard: RaxePortkeyGuard) -> None:
        self._client = client
        self._guard = guard
        self.chat = _ChatWrapper(client.chat, guard)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _ChatWrapper:
    """Wrapper for chat namespace."""

    def __init__(self, chat: Any, guard: RaxePortkeyGuard) -> None:
        self._chat = chat
        self._guard = guard
        self.completions = _CompletionsWrapper(chat.completions, guard)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _CompletionsWrapper:
    """Wrapper for completions namespace."""

    def __init__(self, completions: Any, guard: RaxePortkeyGuard) -> None:
        self._completions = completions
        self._guard = guard

    def create(self, **kwargs: Any) -> Any:
        """Create completion with RAXE scanning."""
        messages = kwargs.get("messages")

        return self._guard.scan_and_call(
            self._completions.create,
            messages=messages,
            **{k: v for k, v in kwargs.items() if k != "messages"},
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


# =============================================================================
# Convenience Factory Functions
# =============================================================================


def create_portkey_guard(
    raxe: "Raxe | None" = None,
    *,
    block_on_threats: bool = False,
    block_severity_threshold: str = "HIGH",
) -> RaxePortkeyGuard:
    """Create a Portkey client guard.

    Args:
        raxe: Raxe client. Created if not provided.
        block_on_threats: Whether to block on threat detection
        block_severity_threshold: Minimum severity to trigger blocking

    Returns:
        Configured RaxePortkeyGuard
    """
    config = PortkeyGuardConfig(
        block_on_threats=block_on_threats,
        block_severity_threshold=block_severity_threshold,
    )
    return RaxePortkeyGuard(raxe, config)


def create_portkey_webhook(
    raxe: "Raxe | None" = None,
    *,
    block_on_threats: bool = False,
    block_severity_threshold: str = "HIGH",
) -> RaxePortkeyWebhook:
    """Create a Portkey webhook handler.

    Args:
        raxe: Raxe client. Created if not provided.
        block_on_threats: Whether to return false verdict on threats
        block_severity_threshold: Minimum severity to trigger blocking

    Returns:
        Configured RaxePortkeyWebhook
    """
    config = PortkeyGuardConfig(
        block_on_threats=block_on_threats,
        block_severity_threshold=block_severity_threshold,
    )
    return RaxePortkeyWebhook(raxe, config)
