"""AgentScanner - Core scanning component for AI agent framework integrations.

This module provides the shared AgentScanner class that all agent framework
integrations (LangChain, CrewAI, AutoGen, LlamaIndex, etc.) use via COMPOSITION.

Design Principles:
- Composition over inheritance: AgentScanner is composed into integrations
- Sync-first with async wrappers: Core logic is synchronous for simplicity
- Default: log-only (blocking requires explicit on_threat="block")
- Privacy-first: No PII in telemetry, only hashes and metadata

Usage:
    from raxe import Raxe
    from raxe.sdk.agent_scanner import AgentScanner, AgentScannerConfig

    # Create scanner with existing Raxe client
    raxe = Raxe()
    config = AgentScannerConfig(
        scan_prompts=True,
        scan_tool_calls=True,
        on_threat="log",  # Default: log only, don't block
    )
    scanner = AgentScanner(raxe=raxe, config=config)

    # Scan a prompt
    result = scanner.scan_prompt("User input here")
    if result.should_block:
        raise ThreatDetectedError(result)

    # Validate a tool call
    tool_result = scanner.validate_tool_call(
        tool_name="shell_execute",
        arguments={"command": "rm -rf /"},
    )
    if not tool_result.is_allowed:
        print(f"Tool blocked: {tool_result.reason}")

See: docs/agent_integrations.md for integration guide.

Version History:
- v1.0: Initial implementation with basic scanning
- v2.0: Redesigned with AgentScannerConfig, improved tool validation,
        async support, and enhanced telemetry (current)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Literal, Pattern

from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import (
    ErrorCode,
    RaxeError,
    RaxeException,
    SecurityException,
)
from raxe.utils.logging import get_logger

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult

logger = get_logger(__name__)


class ScanType(str, Enum):
    """Types of scans in agentic systems.

    Used for telemetry, logging, and per-type configuration.
    """

    PROMPT = "prompt"
    RESPONSE = "response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_ACTION = "agent_action"
    CHAIN_INPUT = "chain_input"
    CHAIN_OUTPUT = "chain_output"
    SYSTEM_PROMPT = "system_prompt"
    RAG_CONTEXT = "rag_context"
    MEMORY_CONTENT = "memory_content"


class ThreatAction(str, Enum):
    """Action to take when a threat is detected.

    Attributes:
        LOG: Log the threat but allow the request to proceed (default)
        BLOCK: Block the request and raise ThreatDetectedError
        WARN: Log a warning and allow (same as LOG but higher visibility)
    """

    LOG = "log"
    BLOCK = "block"
    WARN = "warn"


class ToolValidationMode(str, Enum):
    """How to validate tool calls."""

    DISABLED = "disabled"  # No tool validation
    ALLOWLIST = "allowlist"  # Only allowed tools can execute
    BLOCKLIST = "blocklist"  # Blocked tools cannot execute


class ToolValidationResult(str, Enum):
    """Result of tool validation.

    Attributes:
        ALLOWED: Tool call is allowed to proceed
        BLOCKED: Tool call is blocked (dangerous or blocklisted)
        SUSPICIOUS: Tool call is suspicious but allowed (logged)
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    SUSPICIOUS = "suspicious"


class ScanMode(str, Enum):
    """Scan mode controlling threat response behavior.

    Determines what action to take when threats are detected.

    Attributes:
        LOG_ONLY: Log threats but don't block (default, safe)
        BLOCK_ON_THREAT: Block on any threat detection
        BLOCK_ON_HIGH: Block only on HIGH or CRITICAL severity
        BLOCK_ON_CRITICAL: Block only on CRITICAL severity
    """

    LOG_ONLY = "log_only"
    BLOCK_ON_THREAT = "block_on_threat"
    BLOCK_ON_HIGH = "block_on_high"
    BLOCK_ON_CRITICAL = "block_on_critical"


class MessageType(str, Enum):
    """Type of message in multi-agent communication.

    Used for context-aware scanning and telemetry.

    Attributes:
        HUMAN_INPUT: Direct input from human user
        AGENT_TO_AGENT: Message between agents in a multi-agent system
        AGENT_RESPONSE: Response from an agent to user/system
        FUNCTION_CALL: Tool/function invocation
        FUNCTION_RESULT: Result from tool/function execution
        SYSTEM: System-level message (instructions, config)
    """

    HUMAN_INPUT = "human_input"
    AGENT_TO_AGENT = "agent_to_agent"
    AGENT_RESPONSE = "agent_response"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    SYSTEM = "system"


@dataclass
class ScanContext:
    """Context for a scan operation in multi-agent systems.

    Provides metadata about the message being scanned for
    better threat detection and telemetry.

    Attributes:
        message_type: Type of message (human input, agent-to-agent, etc.)
        sender_name: Name of the sending agent (if applicable)
        receiver_name: Name of the receiving agent (if applicable)
        conversation_id: Unique ID for the conversation thread
        message_index: Position in the conversation (0-indexed)
        metadata: Additional context metadata
    """

    message_type: MessageType
    sender_name: str | None = None
    receiver_name: str | None = None
    conversation_id: str | None = None
    message_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolPolicy:
    """Policy for tool validation.

    Defines which tools are allowed/blocked and any argument restrictions.

    Attributes:
        mode: Validation mode (allowlist, blocklist, or disabled)
        tools: Set of tool names for allowlist/blocklist
        argument_patterns: Dict mapping tool names to forbidden argument patterns
        block_on_violation: Whether to block or just log on policy violation
    """

    mode: ToolValidationMode = ToolValidationMode.DISABLED
    tools: frozenset[str] = field(default_factory=frozenset)
    argument_patterns: dict[str, list[Pattern[str]]] = field(default_factory=dict)
    block_on_violation: bool = True

    @classmethod
    def allow_only(cls, *tools: str, block: bool = True) -> ToolPolicy:
        """Create allowlist policy - only specified tools can run.

        Args:
            *tools: Tool names that are allowed
            block: Whether to block violations (default: True)

        Returns:
            ToolPolicy configured as allowlist

        Example:
            policy = ToolPolicy.allow_only("calculator", "search")
        """
        return cls(
            mode=ToolValidationMode.ALLOWLIST,
            tools=frozenset(tools),
            block_on_violation=block,
        )

    @classmethod
    def block_tools(cls, *tools: str, block: bool = True) -> ToolPolicy:
        """Create blocklist policy - specified tools cannot run.

        Args:
            *tools: Tool names that are blocked
            block: Whether to block violations (default: True)

        Returns:
            ToolPolicy configured as blocklist

        Example:
            policy = ToolPolicy.block_tools("shell", "file_write")
        """
        return cls(
            mode=ToolValidationMode.BLOCKLIST,
            tools=frozenset(tools),
            block_on_violation=block,
        )

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed by this policy.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is allowed, False if blocked
        """
        if self.mode == ToolValidationMode.DISABLED:
            return True
        elif self.mode == ToolValidationMode.ALLOWLIST:
            return tool_name in self.tools
        elif self.mode == ToolValidationMode.BLOCKLIST:
            return tool_name not in self.tools
        return True


@dataclass(frozen=True)
class AgentScanResult:
    """Result from an AgentScanner scan.

    Immutable result containing scan outcome and metadata.
    Used by both scan_prompt() and validate_tool_call().

    Attributes:
        scan_type: Type of scan performed
        has_threats: Whether threats were detected
        should_block: Whether the action should be blocked
        severity: Highest severity detected
        detection_count: Number of detections
        trace_id: Correlation ID for this agent run
        step_id: Step number within the agent run
        duration_ms: Scan duration in milliseconds
        message: Human-readable summary
        details: Additional details (tool name, etc.)
        policy_violation: Whether a tool policy was violated
        rule_ids: List of triggered rule IDs (for debugging)
        families: Threat families detected (PI, JB, etc.)
        prompt_hash: SHA256 hash of scanned content (privacy-preserving)
        action_taken: Action that was/will be taken (log, block, warn)
        pipeline_result: Full ScanPipelineResult (for advanced use)
    """

    scan_type: ScanType
    has_threats: bool
    should_block: bool
    severity: str | None
    detection_count: int
    trace_id: str
    step_id: int
    duration_ms: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    policy_violation: bool = False
    rule_ids: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)
    prompt_hash: str = ""
    action_taken: str = "allow"
    pipeline_result: Any = None  # ScanPipelineResult, optional for advanced use

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation (excludes pipeline_result for privacy)
        """
        return {
            "scan_type": self.scan_type.value,
            "has_threats": self.has_threats,
            "should_block": self.should_block,
            "severity": self.severity,
            "detection_count": self.detection_count,
            "trace_id": self.trace_id,
            "step_id": self.step_id,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "details": self.details,
            "policy_violation": self.policy_violation,
            "rule_ids": self.rule_ids,
            "families": self.families,
            "prompt_hash": self.prompt_hash,
            "action_taken": self.action_taken,
        }


@dataclass(frozen=True)
class ToolValidationResponse:
    """Result of tool call validation.

    Attributes:
        is_allowed: True if tool call should proceed
        result: Validation result enum (ALLOWED, BLOCKED, SUSPICIOUS)
        reason: Human-readable reason for decision
        tool_name: Name of the tool being validated
        is_dangerous: True if tool is on dangerous tools list
        arguments_scanned: True if arguments were scanned for threats
        scan_result: AgentScanResult if arguments were scanned
        metadata: Additional validation metadata
    """

    is_allowed: bool
    result: ToolValidationResult
    reason: str
    tool_name: str
    is_dangerous: bool = False
    arguments_scanned: bool = False
    scan_result: AgentScanResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result_dict = {
            "is_allowed": self.is_allowed,
            "result": self.result.value,
            "reason": self.reason,
            "tool_name": self.tool_name,
            "is_dangerous": self.is_dangerous,
            "arguments_scanned": self.arguments_scanned,
            "metadata": self.metadata,
        }
        if self.scan_result:
            result_dict["scan_result"] = self.scan_result.to_dict()
        return result_dict


@dataclass
class ScanConfig:
    """Configuration for a specific scan type.

    Attributes:
        enabled: Whether this scan type is enabled
        block_on_threat: Whether to block on threat detection
        min_severity_to_block: Minimum severity level to trigger blocking
    """

    enabled: bool = True
    block_on_threat: bool = False  # Default: log-only
    min_severity_to_block: str = "MEDIUM"


@dataclass
class ToolValidationConfig:
    """Configuration for tool call validation.

    Attributes:
        enabled: Enable tool call validation (default: True)
        allowlist: List of explicitly allowed tool names (empty = allow all)
        blocklist: List of explicitly blocked tool names
        scan_arguments: Scan tool arguments for threats (default: True)
        dangerous_tools: Tools considered high-risk requiring extra scrutiny
        argument_patterns_to_scan: Argument names to always scan
        max_argument_length: Maximum argument length to scan
    """

    enabled: bool = True
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    scan_arguments: bool = True
    dangerous_tools: list[str] = field(
        default_factory=lambda: [
            "shell",
            "bash",
            "exec",
            "execute",
            "run_command",
            "shell_execute",
            "code_interpreter",
            "python_repl",
            "eval",
            "subprocess",
            "terminal",
            "ssh",
        ]
    )
    argument_patterns_to_scan: list[str] = field(
        default_factory=lambda: [
            "command",
            "code",
            "script",
            "query",
            "sql",
            "input",
            "prompt",
            "message",
            "content",
            "text",
            "body",
            "url",
            "path",
        ]
    )
    max_argument_length: int = 10000


@dataclass
class AgentScannerConfig:
    """Configuration for AgentScanner behavior.

    This dataclass defines ALL configuration options for the AgentScanner.
    Settings cascade: explicit > environment > defaults.

    Attributes:
        scan_prompts: Scan user prompts before sending to LLM (default: True)
        scan_system_prompts: Scan system prompts for injection (default: True)
        scan_tool_calls: Validate tool calls before execution (default: True)
        scan_tool_results: Scan tool execution results (default: False)
        scan_responses: Scan LLM responses for threats (default: False)
        scan_memory: Scan memory/context retrieved (default: False)
        scan_rag_context: Scan RAG-retrieved context (default: True)

        on_threat: Action when threat detected - "log", "block", or "warn"
        block_severity_threshold: Minimum severity to trigger block
        allow_severity: List of severities to always allow

        tool_validation: Configuration for tool call validation
        confidence_threshold: Minimum confidence to report detections
        l2_enabled: Enable L2 ML detection for agent scans

        on_threat_callback: Optional callback when threat detected
        on_block_callback: Optional callback when request blocked
        telemetry_enabled: Enable agent-specific telemetry

        timeout_ms: Scan timeout in milliseconds
        fail_open: If scan fails/times out, allow request
        max_prompt_length: Maximum prompt length to scan
    """

    # Scan targets
    scan_prompts: bool = True
    scan_system_prompts: bool = True
    scan_tool_calls: bool = True
    scan_tool_results: bool = False
    scan_responses: bool = False
    scan_memory: bool = False
    scan_rag_context: bool = True

    # Threat handling - DEFAULT IS LOG-ONLY (safe default)
    on_threat: Literal["log", "block", "warn"] = "log"
    block_severity_threshold: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = (
        "HIGH"
    )
    allow_severity: list[str] = field(default_factory=list)

    # Tool validation
    tool_validation: ToolValidationConfig = field(
        default_factory=ToolValidationConfig
    )

    # Detection settings
    confidence_threshold: float = 0.5
    l2_enabled: bool = True

    # Callbacks
    on_threat_callback: Callable[[AgentScanResult], None] | None = None
    on_block_callback: Callable[[AgentScanResult], None] | None = None

    # Telemetry
    telemetry_enabled: bool = True

    # Performance
    timeout_ms: float = 100.0
    fail_open: bool = True
    max_prompt_length: int = 50000

    def should_scan(self, scan_type: ScanType) -> bool:
        """Check if a specific scan type should be enabled.

        Args:
            scan_type: The type of content to potentially scan

        Returns:
            True if scanning is enabled for this type
        """
        mapping = {
            ScanType.PROMPT: self.scan_prompts,
            ScanType.SYSTEM_PROMPT: self.scan_system_prompts,
            ScanType.TOOL_CALL: self.scan_tool_calls,
            ScanType.TOOL_RESULT: self.scan_tool_results,
            ScanType.RESPONSE: self.scan_responses,
            ScanType.MEMORY_CONTENT: self.scan_memory,
            ScanType.RAG_CONTEXT: self.scan_rag_context,
            ScanType.AGENT_ACTION: self.scan_prompts,  # Use prompt setting
            ScanType.CHAIN_INPUT: self.scan_prompts,
            ScanType.CHAIN_OUTPUT: self.scan_responses,
        }
        return mapping.get(scan_type, False)


# =============================================================================
# Exceptions
# =============================================================================


class ThreatDetectedError(RaxeException):
    """Raised when a threat is detected and blocking is enabled.

    This exception is raised when:
    - A threat is detected during agent operation
    - The AgentScannerConfig has on_threat="block"
    - The severity meets or exceeds block_severity_threshold

    Attributes:
        result: The AgentScanResult that triggered the block
    """

    def __init__(
        self,
        result: AgentScanResult,
        message: str | None = None,
    ) -> None:
        """Initialize threat detected error.

        Args:
            result: AgentScanResult containing threat details
            message: Optional custom message
        """
        self.result = result

        error = RaxeError(
            code=ErrorCode.SEC_THREAT_DETECTED,
            message=message
            or f"Agent threat detected: {result.severity} severity ({result.detection_count} detection(s))",
            details={
                "severity": result.severity,
                "threat_count": result.detection_count,
                "scan_type": result.scan_type.value,
                "rule_ids": result.rule_ids[:5],
                "families": result.families,
            },
            remediation="Review the detected threat. If false positive, adjust "
            "AgentScannerConfig.allow_severity or add a suppression rule.",
        )

        super().__init__(error)


class ToolBlockedError(RaxeException):
    """Raised when a tool call is blocked.

    Attributes:
        response: The ToolValidationResponse that triggered the block
    """

    def __init__(
        self,
        response: ToolValidationResponse,
        message: str | None = None,
    ) -> None:
        """Initialize tool blocked error."""
        self.response = response

        error = RaxeError(
            code=ErrorCode.SEC_BLOCKED_BY_POLICY,
            message=message or f"Tool blocked: {response.tool_name} - {response.reason}",
            details={
                "tool_name": response.tool_name,
                "reason": response.reason,
                "is_dangerous": response.is_dangerous,
            },
            remediation="Review tool validation config. Add tool to allowlist if safe.",
        )

        super().__init__(error)


class AgentScanner:
    """Unified scanner for agentic AI systems.

    This class provides a composable scanner that can be integrated with
    any agentic framework. It handles:
    - Prompt and response scanning
    - Tool call validation and argument scanning
    - Agent action monitoring
    - Trace-aware scanning with correlation IDs

    Use via composition in framework-specific integrations:
    - LangChain: RaxeCallbackHandler wraps AgentScanner
    - LlamaIndex: RaxeQueryEngine wraps AgentScanner
    - Custom: Direct AgentScanner usage

    Attributes:
        raxe: Underlying Raxe client for scanning
        tool_policy: Policy for tool validation
        scan_configs: Per-scan-type configuration

    Example:
        >>> scanner = AgentScanner()
        >>> result = scanner.scan_tool_call("search", {"query": user_input})
        >>> if result.should_block:
        ...     raise SecurityError(result.message)
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        tool_policy: ToolPolicy | None = None,
        default_block: bool = False,
        scan_configs: dict[ScanType, ScanConfig] | None = None,
        on_threat: Callable[[AgentScanResult], None] | None = None,
    ) -> None:
        """Initialize AgentScanner.

        Args:
            raxe_client: Optional Raxe instance (creates default if None)
            tool_policy: Policy for tool validation (default: no restrictions)
            default_block: Default blocking behavior (default: False = log-only)
            scan_configs: Per-scan-type configuration overrides
            on_threat: Optional callback invoked when threat detected

        Example:
            # Basic usage with defaults
            scanner = AgentScanner()

            # With tool restrictions
            scanner = AgentScanner(
                tool_policy=ToolPolicy.block_tools("shell", "file_write")
            )

            # Blocking mode for prompts only
            scanner = AgentScanner(
                scan_configs={
                    ScanType.PROMPT: ScanConfig(block_on_threat=True),
                    ScanType.RESPONSE: ScanConfig(block_on_threat=False),
                }
            )
        """
        self.raxe = raxe_client or Raxe()
        self.tool_policy = tool_policy or ToolPolicy()
        self.default_block = default_block
        self.on_threat = on_threat

        # Initialize default scan configs
        self._scan_configs: dict[ScanType, ScanConfig] = {
            scan_type: ScanConfig(block_on_threat=default_block)
            for scan_type in ScanType
        }

        # Apply custom configs
        if scan_configs:
            for scan_type, config in scan_configs.items():
                self._scan_configs[scan_type] = config

        # Trace management
        self._current_trace_id: str | None = None
        self._step_counter: int = 0

        logger.debug(
            "AgentScanner initialized",
            extra={
                "tool_policy_mode": self.tool_policy.mode.value,
                "default_block": default_block,
            },
        )

    def start_trace(self, trace_id: str | None = None) -> str:
        """Start a new agent trace for correlation.

        Call this at the start of an agent run to enable step correlation.

        Args:
            trace_id: Optional custom trace ID (generates UUID if None)

        Returns:
            The trace ID being used

        Example:
            trace_id = scanner.start_trace()
            # ... agent execution ...
            scanner.end_trace()
        """
        self._current_trace_id = trace_id or str(uuid.uuid4())
        self._step_counter = 0
        logger.debug(f"Started agent trace: {self._current_trace_id}")
        return self._current_trace_id

    def end_trace(self) -> None:
        """End the current agent trace."""
        if self._current_trace_id:
            logger.debug(
                f"Ended agent trace: {self._current_trace_id}, "
                f"steps: {self._step_counter}"
            )
        self._current_trace_id = None
        self._step_counter = 0

    def _get_trace_id(self) -> str:
        """Get current trace ID or generate one."""
        return self._current_trace_id or str(uuid.uuid4())

    def _next_step(self) -> int:
        """Increment and return step counter."""
        self._step_counter += 1
        return self._step_counter

    def _build_result(
        self,
        scan_type: ScanType,
        has_threats: bool,
        should_block: bool,
        severity: str | None,
        detection_count: int,
        duration_ms: float,
        message: str,
        details: dict[str, Any] | None = None,
        policy_violation: bool = False,
        content: str | None = None,
    ) -> AgentScanResult:
        """Build an AgentScanResult with trace context.

        Args:
            content: The scanned content (used for hash, NOT stored in result)
        """
        # Compute privacy-preserving hash of content
        prompt_hash = ""
        if content:
            prompt_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

        # Determine action taken
        action_taken = "allow"
        if has_threats:
            action_taken = "block" if should_block else "log"

        return AgentScanResult(
            scan_type=scan_type,
            has_threats=has_threats,
            should_block=should_block,
            severity=severity,
            detection_count=detection_count,
            trace_id=self._get_trace_id(),
            step_id=self._next_step(),
            duration_ms=duration_ms,
            message=message,
            details=details or {},
            policy_violation=policy_violation,
            prompt_hash=prompt_hash,
            action_taken=action_taken,
        )

    def _should_block(
        self,
        scan_type: ScanType,
        severity: str | None,
    ) -> bool:
        """Determine if action should be blocked based on config and severity."""
        config = self._scan_configs.get(scan_type)
        if not config or not config.block_on_threat:
            return False

        if not severity:
            return False

        # Severity ordering
        severity_order = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        min_severity = severity_order.get(config.min_severity_to_block, 2)
        actual_severity = severity_order.get(severity.upper(), 0)

        return actual_severity >= min_severity

    def scan_prompt(
        self,
        prompt: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Scan a prompt before sending to LLM.

        Args:
            prompt: The prompt text to scan
            metadata: Optional metadata about the prompt

        Returns:
            AgentScanResult with scan results

        Raises:
            SecurityException: If blocking enabled and threat detected
        """
        if not prompt or not prompt.strip():
            return self._build_result(
                scan_type=ScanType.PROMPT,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=0.0,
                message="Empty prompt skipped",
                content=prompt,
            )

        start = time.perf_counter()
        config = self._scan_configs[ScanType.PROMPT]

        try:
            result = self.raxe.scan(
                prompt,
                block_on_threat=config.block_on_threat,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            should_block = self._should_block(ScanType.PROMPT, result.severity)

            agent_result = self._build_result(
                scan_type=ScanType.PROMPT,
                has_threats=result.has_threats,
                should_block=should_block,
                severity=result.severity,
                detection_count=result.total_detections,
                duration_ms=duration_ms,
                message=f"Prompt scan: {result.severity or 'clean'}"
                if result.has_threats
                else "Prompt scan: clean",
                details=metadata,
                content=prompt,
            )

            if result.has_threats and self.on_threat:
                self.on_threat(agent_result)

            return agent_result

        except SecurityException:
            duration_ms = (time.perf_counter() - start) * 1000
            raise

    def scan_response(
        self,
        response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Scan an LLM response.

        Args:
            response: The response text to scan
            metadata: Optional metadata about the response

        Returns:
            AgentScanResult with scan results

        Raises:
            SecurityException: If blocking enabled and threat detected
        """
        if not response or not response.strip():
            return self._build_result(
                scan_type=ScanType.RESPONSE,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=0.0,
                message="Empty response skipped",
                content=response,
            )

        start = time.perf_counter()
        config = self._scan_configs[ScanType.RESPONSE]

        try:
            result = self.raxe.scan(
                response,
                block_on_threat=config.block_on_threat,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            should_block = self._should_block(ScanType.RESPONSE, result.severity)

            agent_result = self._build_result(
                scan_type=ScanType.RESPONSE,
                has_threats=result.has_threats,
                should_block=should_block,
                severity=result.severity,
                detection_count=result.total_detections,
                duration_ms=duration_ms,
                message=f"Response scan: {result.severity or 'clean'}"
                if result.has_threats
                else "Response scan: clean",
                details=metadata,
                content=response,
            )

            if result.has_threats and self.on_threat:
                self.on_threat(agent_result)

            return agent_result

        except SecurityException:
            duration_ms = (time.perf_counter() - start) * 1000
            raise

    def validate_tool(self, tool_name: str) -> tuple[bool, str]:
        """Validate a tool against the policy (without scanning arguments).

        Args:
            tool_name: Name of the tool to validate

        Returns:
            Tuple of (is_allowed, message)
        """
        if self.tool_policy.mode == ToolValidationMode.DISABLED:
            return True, "Tool validation disabled"

        is_allowed = self.tool_policy.is_tool_allowed(tool_name)

        if not is_allowed:
            if self.tool_policy.mode == ToolValidationMode.ALLOWLIST:
                return False, f"Tool '{tool_name}' not in allowlist"
            else:
                return False, f"Tool '{tool_name}' is blocked"

        return True, "Tool allowed"

    def scan_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Scan a tool call before execution.

        This method:
        1. Validates tool against policy (allowlist/blocklist)
        2. Scans tool arguments for threats
        3. Checks arguments against forbidden patterns

        Args:
            tool_name: Name of the tool being called
            tool_args: Tool arguments (dict or string)
            metadata: Optional metadata about the tool call

        Returns:
            AgentScanResult with validation and scan results

        Raises:
            SecurityException: If blocking enabled and threat/violation detected
        """
        start = time.perf_counter()
        config = self._scan_configs[ScanType.TOOL_CALL]
        details = {"tool_name": tool_name, **(metadata or {})}

        # Step 1: Validate tool against policy
        is_allowed, policy_message = self.validate_tool(tool_name)

        if not is_allowed:
            duration_ms = (time.perf_counter() - start) * 1000
            agent_result = self._build_result(
                scan_type=ScanType.TOOL_CALL,
                has_threats=True,
                should_block=self.tool_policy.block_on_violation,
                severity="CRITICAL",
                detection_count=1,
                duration_ms=duration_ms,
                message=policy_message,
                details=details,
                policy_violation=True,
                content=tool_name,  # Hash tool name for policy violations
            )

            if self.on_threat:
                self.on_threat(agent_result)

            if self.tool_policy.block_on_violation:
                # Log and raise - create a minimal scan result for the exception
                logger.warning(
                    f"Tool policy violation: {policy_message}",
                    extra={"tool_name": tool_name},
                )
                # We need to create a ScanPipelineResult for the exception
                # For now, just log and return the result
                # The caller should check should_block and handle accordingly

            return agent_result

        # Step 2: Convert args to string for scanning
        if isinstance(tool_args, dict):
            # Scan values, not keys (to avoid false positives on key names)
            args_text = " ".join(str(v) for v in tool_args.values() if v)
        else:
            args_text = str(tool_args)

        if not args_text or not args_text.strip():
            return self._build_result(
                scan_type=ScanType.TOOL_CALL,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=(time.perf_counter() - start) * 1000,
                message=f"Tool '{tool_name}' call: clean (no args)",
                details=details,
                content=tool_name,  # Hash tool name for empty args case
            )

        # Step 3: Check forbidden argument patterns for this tool
        if tool_name in self.tool_policy.argument_patterns:
            for pattern in self.tool_policy.argument_patterns[tool_name]:
                if pattern.search(args_text):
                    duration_ms = (time.perf_counter() - start) * 1000
                    return self._build_result(
                        scan_type=ScanType.TOOL_CALL,
                        has_threats=True,
                        should_block=self.tool_policy.block_on_violation,
                        severity="HIGH",
                        detection_count=1,
                        duration_ms=duration_ms,
                        message=f"Tool '{tool_name}' argument matches forbidden pattern",
                        details=details,
                        policy_violation=True,
                        content=args_text,  # Hash args for forbidden pattern match
                    )

        # Step 4: Scan arguments for threats
        try:
            result = self.raxe.scan(
                args_text,
                block_on_threat=config.block_on_threat,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            should_block = self._should_block(ScanType.TOOL_CALL, result.severity)

            agent_result = self._build_result(
                scan_type=ScanType.TOOL_CALL,
                has_threats=result.has_threats,
                should_block=should_block,
                severity=result.severity,
                detection_count=result.total_detections,
                duration_ms=duration_ms,
                message=f"Tool '{tool_name}' call: {result.severity or 'clean'}"
                if result.has_threats
                else f"Tool '{tool_name}' call: clean",
                details=details,
                content=args_text,  # Hash args for main scan result
            )

            if result.has_threats and self.on_threat:
                self.on_threat(agent_result)

            return agent_result

        except SecurityException:
            duration_ms = (time.perf_counter() - start) * 1000
            raise

    def scan_tool_result(
        self,
        tool_name: str,
        result: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Scan a tool result after execution.

        Args:
            tool_name: Name of the tool that produced the result
            result: The tool's output to scan
            metadata: Optional metadata about the tool result

        Returns:
            AgentScanResult with scan results

        Raises:
            SecurityException: If blocking enabled and threat detected
        """
        if not result or not result.strip():
            return self._build_result(
                scan_type=ScanType.TOOL_RESULT,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=0.0,
                message=f"Tool '{tool_name}' result: empty",
                details={"tool_name": tool_name, **(metadata or {})},
                content=tool_name,  # Hash tool name for empty result case
            )

        start = time.perf_counter()
        config = self._scan_configs[ScanType.TOOL_RESULT]
        details = {"tool_name": tool_name, **(metadata or {})}

        try:
            scan_result = self.raxe.scan(
                result,
                block_on_threat=config.block_on_threat,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            should_block = self._should_block(ScanType.TOOL_RESULT, scan_result.severity)

            agent_result = self._build_result(
                scan_type=ScanType.TOOL_RESULT,
                has_threats=scan_result.has_threats,
                should_block=should_block,
                severity=scan_result.severity,
                detection_count=scan_result.total_detections,
                duration_ms=duration_ms,
                message=f"Tool '{tool_name}' result: {scan_result.severity or 'clean'}"
                if scan_result.has_threats
                else f"Tool '{tool_name}' result: clean",
                details=details,
                content=result,  # Hash tool result content
            )

            if scan_result.has_threats and self.on_threat:
                self.on_threat(agent_result)

            return agent_result

        except SecurityException:
            duration_ms = (time.perf_counter() - start) * 1000
            raise

    def scan_agent_action(
        self,
        action_type: str,
        action_input: str | dict[str, Any],
        *,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Scan an agent action.

        Args:
            action_type: Type of action (e.g., "tool_call", "final_answer")
            action_input: The action's input to scan
            tool_name: Optional tool name if action is a tool call
            metadata: Optional metadata about the action

        Returns:
            AgentScanResult with scan results

        Raises:
            SecurityException: If blocking enabled and threat detected
        """
        # If this is a tool call, delegate to scan_tool_call
        if tool_name and action_type == "tool_call":
            args = action_input if isinstance(action_input, dict) else {"input": action_input}
            return self.scan_tool_call(tool_name, args, metadata=metadata)

        # Otherwise, scan the action input as text
        if isinstance(action_input, dict):
            input_text = " ".join(str(v) for v in action_input.values() if v)
        else:
            input_text = str(action_input)

        if not input_text or not input_text.strip():
            return self._build_result(
                scan_type=ScanType.AGENT_ACTION,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=0.0,
                message=f"Agent action '{action_type}': empty input",
                details={"action_type": action_type, **(metadata or {})},
                content=action_type,  # Hash action type for empty input case
            )

        start = time.perf_counter()
        config = self._scan_configs[ScanType.AGENT_ACTION]
        details = {"action_type": action_type, "tool_name": tool_name, **(metadata or {})}

        try:
            result = self.raxe.scan(
                input_text,
                block_on_threat=config.block_on_threat,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            should_block = self._should_block(ScanType.AGENT_ACTION, result.severity)

            agent_result = self._build_result(
                scan_type=ScanType.AGENT_ACTION,
                has_threats=result.has_threats,
                should_block=should_block,
                severity=result.severity,
                detection_count=result.total_detections,
                duration_ms=duration_ms,
                message=f"Agent action '{action_type}': {result.severity or 'clean'}"
                if result.has_threats
                else f"Agent action '{action_type}': clean",
                details=details,
                content=input_text,  # Hash action input
            )

            if result.has_threats and self.on_threat:
                self.on_threat(agent_result)

            return agent_result

        except SecurityException:
            duration_ms = (time.perf_counter() - start) * 1000
            raise

    def get_config(self, scan_type: ScanType) -> ScanConfig:
        """Get configuration for a scan type.

        Args:
            scan_type: The scan type to get config for

        Returns:
            ScanConfig for the specified type
        """
        return self._scan_configs.get(scan_type, ScanConfig())

    def set_config(self, scan_type: ScanType, config: ScanConfig) -> None:
        """Set configuration for a scan type.

        Args:
            scan_type: The scan type to configure
            config: The configuration to apply
        """
        self._scan_configs[scan_type] = config

    # =========================================================================
    # New validate_tool_call method (returns ToolValidationResponse)
    # =========================================================================

    def validate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
        raise_on_block: bool = False,
    ) -> ToolValidationResponse:
        """Validate a tool call before execution.

        This is a new method that returns ToolValidationResponse with detailed
        validation information. Checks tool against allowlist/blocklist and
        optionally scans arguments for threats.

        Validation order:
        1. Check blocklist (blocked if present)
        2. Check allowlist (if non-empty, must be present)
        3. Check if tool is dangerous (requires extra scrutiny)
        4. Scan arguments if configured

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments to validate (optional)
            context: Optional context metadata
            raise_on_block: Raise ToolBlockedError if blocked

        Returns:
            ToolValidationResponse with validation outcome

        Raises:
            ToolBlockedError: If raise_on_block=True and tool is blocked

        Example:
            response = scanner.validate_tool_call(
                tool_name="shell_execute",
                arguments={"command": "ls -la"},
            )
            if not response.is_allowed:
                print(f"Tool blocked: {response.reason}")
        """
        # Get tool validation config (use ToolValidationConfig if available via AgentScannerConfig)
        # For backward compatibility, also check tool_policy
        tool_name_lower = tool_name.lower()

        # Check against existing tool_policy (backward compatibility)
        if self.tool_policy.mode != ToolValidationMode.DISABLED:
            if not self.tool_policy.is_tool_allowed(tool_name):
                reason = (
                    f"Tool '{tool_name}' not in allowlist"
                    if self.tool_policy.mode == ToolValidationMode.ALLOWLIST
                    else f"Tool '{tool_name}' is blocked"
                )
                response = ToolValidationResponse(
                    is_allowed=False,
                    result=ToolValidationResult.BLOCKED,
                    reason=reason,
                    tool_name=tool_name,
                    metadata={"blocked_by": self.tool_policy.mode.value},
                )
                if raise_on_block:
                    raise ToolBlockedError(response)
                return response

        # Check if tool is dangerous (based on common dangerous tool names)
        dangerous_tools = [
            "shell", "bash", "exec", "execute", "run_command",
            "shell_execute", "code_interpreter", "python_repl",
            "eval", "subprocess", "terminal", "ssh",
        ]
        is_dangerous = any(dt in tool_name_lower for dt in dangerous_tools)

        # Scan arguments if provided
        scan_result: AgentScanResult | None = None
        arguments_scanned = False

        if arguments:
            # Convert args to string for scanning
            if isinstance(arguments, dict):
                args_text = " ".join(str(v) for v in arguments.values() if v)
            else:
                args_text = str(arguments)

            if args_text and args_text.strip():
                # Scan the arguments
                scan_result = self.scan_tool_call(
                    tool_name,
                    arguments,
                    metadata=context,
                )
                arguments_scanned = True

                # Block if scan result says to block
                if scan_result.should_block:
                    response = ToolValidationResponse(
                        is_allowed=False,
                        result=ToolValidationResult.BLOCKED,
                        reason=f"Threat detected in {tool_name} arguments: {scan_result.severity}",
                        tool_name=tool_name,
                        is_dangerous=is_dangerous,
                        arguments_scanned=True,
                        scan_result=scan_result,
                        metadata={
                            "blocked_by": "argument_scan",
                            "severity": scan_result.severity,
                        },
                    )
                    if raise_on_block:
                        raise ToolBlockedError(response)
                    return response

                # Mark as suspicious if threats found but not blocking
                if scan_result.has_threats:
                    return ToolValidationResponse(
                        is_allowed=True,
                        result=ToolValidationResult.SUSPICIOUS,
                        reason=f"Suspicious content in arguments: {scan_result.severity}",
                        tool_name=tool_name,
                        is_dangerous=is_dangerous,
                        arguments_scanned=True,
                        scan_result=scan_result,
                    )

        # Tool allowed
        return ToolValidationResponse(
            is_allowed=True,
            result=ToolValidationResult.ALLOWED,
            reason="Tool validation passed",
            tool_name=tool_name,
            is_dangerous=is_dangerous,
            arguments_scanned=arguments_scanned,
            scan_result=scan_result,
        )

    # =========================================================================
    # Async Variants
    # =========================================================================

    async def scan_prompt_async(
        self,
        prompt: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Async wrapper for scan_prompt.

        Runs the synchronous scan in a thread pool executor.

        Args:
            prompt: The prompt text to scan
            metadata: Optional metadata about the prompt

        Returns:
            AgentScanResult with scan results
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan_prompt(prompt, metadata=metadata),
        )

    async def scan_response_async(
        self,
        response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Async wrapper for scan_response."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan_response(response, metadata=metadata),
        )

    async def scan_tool_call_async(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Async wrapper for scan_tool_call."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan_tool_call(tool_name, tool_args, metadata=metadata),
        )

    async def validate_tool_call_async(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
        raise_on_block: bool = False,
    ) -> ToolValidationResponse:
        """Async wrapper for validate_tool_call."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.validate_tool_call(
                tool_name,
                arguments,
                context=context,
                raise_on_block=raise_on_block,
            ),
        )

    async def scan_agent_action_async(
        self,
        action_type: str,
        action_input: str | dict[str, Any],
        *,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentScanResult:
        """Async wrapper for scan_agent_action."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan_agent_action(
                action_type,
                action_input,
                tool_name=tool_name,
                metadata=metadata,
            ),
        )

    # =========================================================================
    # Telemetry Methods
    # =========================================================================

    def _emit_agent_telemetry(
        self,
        result: AgentScanResult,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Emit agent-specific telemetry (non-blocking).

        Telemetry is privacy-preserving:
        - prompt_hash (SHA256)
        - metadata and counts only
        - NO actual prompt content

        Args:
            result: The scan result to track
            context: Optional context metadata
        """
        try:
            from raxe.application.telemetry_orchestrator import get_orchestrator

            orchestrator = get_orchestrator()
            if orchestrator is None or not orchestrator.is_enabled():
                return

            # Track as feature usage for agent-specific metrics
            orchestrator.track_feature_usage(
                feature="integration_agent",
                action="completed" if not result.has_threats else "invoked",
                duration_ms=result.duration_ms,
                success=True,
                metadata={
                    "scan_type": result.scan_type.value,
                    "has_threats": result.has_threats,
                    "severity": result.severity,
                    "action_taken": result.action_taken,
                    "trace_id": result.trace_id,
                    "step_id": result.step_id,
                    "framework": context.get("framework") if context else None,
                },
            )
        except Exception as e:
            # Never let telemetry break scanning
            logger.debug(f"Agent telemetry error (non-blocking): {e}")

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def should_block_result(self, result: AgentScanResult) -> bool:
        """Determine if a scan result should trigger blocking.

        Useful for checking results from external scans.

        Args:
            result: Scan result to check

        Returns:
            True if the result should trigger blocking
        """
        return result.should_block or result.policy_violation

    def scan_rag_context(
        self,
        documents: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[AgentScanResult]:
        """Scan RAG-retrieved documents for threats.

        Args:
            documents: List of document texts to scan
            metadata: Optional context metadata

        Returns:
            List of AgentScanResult, one per document
        """
        results = []
        for i, doc in enumerate(documents):
            doc_metadata = {**(metadata or {}), "document_index": i}
            # Use scan_prompt with RAG_CONTEXT config
            result = self._build_result(
                scan_type=ScanType.RAG_CONTEXT,
                has_threats=False,
                should_block=False,
                severity=None,
                detection_count=0,
                duration_ms=0.0,
                message="RAG context scan",
                details=doc_metadata,
                content=doc if doc else f"doc_{i}",  # Hash document content
            )

            if doc and doc.strip():
                start = time.perf_counter()
                try:
                    scan_result = self.raxe.scan(doc)
                    duration_ms = (time.perf_counter() - start) * 1000
                    result = self._build_result(
                        scan_type=ScanType.RAG_CONTEXT,
                        has_threats=scan_result.has_threats,
                        should_block=self._should_block(ScanType.RAG_CONTEXT, scan_result.severity),
                        severity=scan_result.severity,
                        detection_count=scan_result.total_detections,
                        duration_ms=duration_ms,
                        message=f"RAG context: {scan_result.severity or 'clean'}",
                        details=doc_metadata,
                        content=doc,  # Hash document content
                    )
                except Exception as e:
                    logger.warning(f"RAG context scan failed: {e}")

            results.append(result)
        return results

    async def scan_rag_context_async(
        self,
        documents: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[AgentScanResult]:
        """Async version of scan_rag_context with parallel scanning."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan_rag_context(documents, metadata=metadata),
        )

    def scan_message(
        self,
        text: str,
        *,
        context: ScanContext | None = None,
    ) -> AgentScanResult:
        """Scan a message with context-aware routing.

        This method provides a simplified interface for scanning messages
        in multi-agent systems. It routes to the appropriate scan method
        based on the message type in the context.

        Args:
            text: Message text to scan
            context: Optional context with message type and metadata

        Returns:
            AgentScanResult with scan results

        Example:
            >>> result = scanner.scan_message(
            ...     "User input here",
            ...     context=ScanContext(
            ...         message_type=MessageType.HUMAN_INPUT,
            ...         sender_name="user",
            ...     )
            ... )
        """
        if context is None:
            context = ScanContext(message_type=MessageType.AGENT_TO_AGENT)

        metadata = {
            "sender_name": context.sender_name,
            "receiver_name": context.receiver_name,
            "conversation_id": context.conversation_id,
            "message_index": context.message_index,
            **context.metadata,
        }

        # Route to appropriate method based on message type
        if context.message_type == MessageType.HUMAN_INPUT:
            return self.scan_prompt(text, metadata=metadata)
        elif context.message_type == MessageType.AGENT_RESPONSE:
            return self.scan_response(text, metadata=metadata)
        elif context.message_type == MessageType.FUNCTION_CALL:
            return self.scan_agent_action("function_call", text, metadata=metadata)
        elif context.message_type == MessageType.FUNCTION_RESULT:
            return self.scan_tool_result("unknown", text, metadata=metadata)
        else:
            # Default to prompt scanning for other message types
            return self.scan_prompt(text, metadata=metadata)

    def get_stats(self) -> dict[str, Any]:
        """Get scanner statistics.

        Returns:
            Dictionary with scan metrics
        """
        return {
            "trace_id": self._current_trace_id,
            "step_count": self._step_counter,
            "tool_policy_mode": self.tool_policy.mode.value,
            "default_block": self.default_block,
        }

    def __repr__(self) -> str:
        """String representation of AgentScanner."""
        return (
            f"AgentScanner("
            f"tool_policy={self.tool_policy.mode.value}, "
            f"default_block={self.default_block}, "
            f"trace_id={self._current_trace_id})"
        )


# =============================================================================
# Factory Function for AgentScannerConfig-based initialization
# =============================================================================


def create_agent_scanner(
    raxe: Raxe | None = None,
    config: AgentScannerConfig | None = None,
) -> AgentScanner:
    """Factory function to create AgentScanner with AgentScannerConfig.

    This is the recommended way to create an AgentScanner with the new
    configuration system.

    Args:
        raxe: Optional Raxe client (creates default if None)
        config: AgentScannerConfig (uses defaults if None)

    Returns:
        Configured AgentScanner instance

    Example:
        config = AgentScannerConfig(
            on_threat="block",
            scan_tool_calls=True,
            tool_validation=ToolValidationConfig(
                blocklist=["dangerous_tool"],
            ),
        )
        scanner = create_agent_scanner(config=config)
    """
    config = config or AgentScannerConfig()

    # Build ToolPolicy from ToolValidationConfig
    tool_config = config.tool_validation
    if tool_config.blocklist:
        tool_policy = ToolPolicy.block_tools(
            *tool_config.blocklist,
            block=config.on_threat == "block",
        )
    elif tool_config.allowlist:
        tool_policy = ToolPolicy.allow_only(
            *tool_config.allowlist,
            block=config.on_threat == "block",
        )
    else:
        tool_policy = ToolPolicy()

    # Build scan configs from AgentScannerConfig
    scan_configs: dict[ScanType, ScanConfig] = {}
    for scan_type in ScanType:
        enabled = config.should_scan(scan_type)
        block_on_threat = config.on_threat == "block"
        scan_configs[scan_type] = ScanConfig(
            enabled=enabled,
            block_on_threat=block_on_threat,
            min_severity_to_block=config.block_severity_threshold,
        )

    return AgentScanner(
        raxe_client=raxe,
        tool_policy=tool_policy,
        default_block=config.on_threat == "block",
        scan_configs=scan_configs,
        on_threat=config.on_threat_callback,
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Core class
    "AgentScanner",
    # Factory
    "create_agent_scanner",
    # Configuration
    "AgentScannerConfig",
    "ToolValidationConfig",
    "ScanConfig",
    "ToolPolicy",
    # Result types
    "AgentScanResult",
    "ToolValidationResponse",
    # Enums
    "ScanType",
    "ThreatAction",
    "ToolValidationMode",
    "ToolValidationResult",
    # Exceptions
    "ThreatDetectedError",
    "ToolBlockedError",
]
