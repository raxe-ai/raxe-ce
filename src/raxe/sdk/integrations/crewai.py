"""CrewAI integration for RAXE scanning.

Provides a guard wrapper for automatic RAXE scanning in CrewAI multi-agent
applications. Supports scanning of agent messages, task outputs, tool calls,
and inter-agent communications.

This integration works with:
    - Crew orchestration (kickoff, step_callback, task_callback)
    - Individual Agents
    - Tasks and their outputs
    - Tools (BaseTool subclasses)

Requires: crewai>=0.28.0

Usage:
    from crewai import Crew, Agent, Task
    from raxe import Raxe
    from raxe.sdk.integrations import RaxeCrewGuard

    # Create guard
    guard = RaxeCrewGuard(Raxe())

    # Wrap a crew for automatic scanning
    protected_crew = guard.protect_crew(crew)
    result = protected_crew.kickoff()

    # Or use callbacks directly
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        step_callback=guard.step_callback,
        task_callback=guard.task_callback,
    )
"""

from __future__ import annotations

import functools
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from raxe.sdk.agent_scanner import (
    AgentScanner,
    AgentScannerConfig,
    AgentScanResult,
    MessageType,
    ScanContext,
    ScanMode,
    ThreatDetectedError,
    create_agent_scanner,
)
from raxe.sdk.exceptions import SecurityException
from raxe.sdk.integrations.extractors import (
    extract_text_from_dict,
)

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)

# Type variables for generic typing
T = TypeVar("T")
CrewType = TypeVar("CrewType")
AgentType = TypeVar("AgentType")
TaskType = TypeVar("TaskType")


@dataclass
class CrewGuardConfig:
    """Configuration for RaxeCrewGuard.

    Extends AgentScannerConfig with CrewAI-specific options.

    Attributes:
        mode: How to handle detected threats (default: LOG_ONLY)
        scan_step_outputs: Scan step outputs in step_callback
        scan_task_outputs: Scan task outputs in task_callback
        scan_tool_inputs: Scan tool inputs before execution
        scan_tool_outputs: Scan tool outputs after execution
        scan_agent_thoughts: Scan agent reasoning/thoughts
        scan_crew_inputs: Scan inputs to crew.kickoff()
        scan_crew_outputs: Scan final crew outputs
        on_threat: Callback when threat detected
        on_block: Callback when execution blocked
        wrap_tools: Automatically wrap tools for scanning
        tool_scan_mode: Scan mode specifically for tools

    Example:
        # Monitoring mode (default - safe for production)
        config = CrewGuardConfig()

        # Strict mode for development/testing
        config = CrewGuardConfig(
            mode=ScanMode.BLOCK_ON_HIGH,
            wrap_tools=True,
        )

        # Custom threat handling
        def alert_security(msg, result):
            send_slack_alert(f"Threat: {result.severity}")

        config = CrewGuardConfig(
            on_threat=alert_security,
        )
    """

    # Scanning mode
    mode: ScanMode = ScanMode.LOG_ONLY

    # What to scan
    scan_step_outputs: bool = True
    scan_task_outputs: bool = True
    scan_tool_inputs: bool = True
    scan_tool_outputs: bool = True
    scan_agent_thoughts: bool = True
    scan_crew_inputs: bool = True
    scan_crew_outputs: bool = True

    # Callbacks
    on_threat: Callable[[str, ScanPipelineResult], None] | None = None
    on_block: Callable[[str, ScanPipelineResult], None] | None = None

    # Tool-specific options
    wrap_tools: bool = False  # Auto-wrap tools for scanning
    tool_scan_mode: ScanMode | None = None  # Override mode for tools

    # Advanced options
    include_agent_context: bool = True  # Include agent name/role in scans
    include_task_context: bool = True  # Include task description in scans
    max_thought_length: int = 5000  # Max length of thoughts to scan

    def _mode_to_on_threat(self) -> str:
        """Convert ScanMode to on_threat literal.

        Returns:
            'log', 'block', or 'warn' based on mode
        """
        if self.mode == ScanMode.LOG_ONLY:
            return "log"
        elif self.mode in (
            ScanMode.BLOCK_ON_THREAT,
            ScanMode.BLOCK_ON_HIGH,
            ScanMode.BLOCK_ON_CRITICAL,
        ):
            return "block"
        return "log"

    def _mode_to_severity_threshold(self) -> str:
        """Convert ScanMode to block_severity_threshold.

        Returns:
            Severity threshold based on mode
        """
        if self.mode == ScanMode.BLOCK_ON_CRITICAL:
            return "CRITICAL"
        elif self.mode == ScanMode.BLOCK_ON_HIGH:
            return "HIGH"
        return "HIGH"  # Default for BLOCK_ON_THREAT

    def to_agent_scanner_config(self) -> AgentScannerConfig:
        """Convert to AgentScannerConfig for base scanner.

        Returns:
            AgentScannerConfig with equivalent settings
        """
        # Create wrapper callbacks that adapt CrewAI signature to AgentScanner signature
        # CrewAI: Callable[[str, ScanPipelineResult], None]
        # AgentScanner: Callable[[AgentScanResult], None]
        threat_callback = None
        block_callback = None

        if self.on_threat is not None:
            original_threat = self.on_threat

            def threat_callback(result: AgentScanResult) -> None:
                # Adapt to CrewAI callback signature
                original_threat(result.message, result.pipeline_result)

        if self.on_block is not None:
            original_block = self.on_block

            def block_callback(result: AgentScanResult) -> None:
                original_block(result.message, result.pipeline_result)

        return AgentScannerConfig(
            on_threat=self._mode_to_on_threat(),
            block_severity_threshold=self._mode_to_severity_threshold(),
            scan_prompts=self.scan_crew_inputs,
            scan_system_prompts=self.scan_agent_thoughts,
            scan_tool_calls=self.scan_tool_inputs,
            scan_tool_results=self.scan_tool_outputs,
            scan_responses=self.scan_crew_outputs,
            on_threat_callback=threat_callback,
            on_block_callback=block_callback,
        )


@dataclass
class CrewScanStats:
    """Thread-safe statistics for scans performed during crew execution.

    Tracks scan counts, threats detected, and performance metrics
    across a crew's lifecycle. All operations are thread-safe.

    Attributes:
        total_scans: Total number of scans performed
        step_scans: Number of step_callback scans
        task_scans: Number of task_callback scans
        tool_scans: Number of tool scans
        threats_detected: Total threats detected
        threats_blocked: Number of times execution was blocked
        highest_severity: Highest severity threat seen
        scan_durations_ms: List of scan durations
    """

    total_scans: int = 0
    step_scans: int = 0
    task_scans: int = 0
    tool_scans: int = 0
    threats_detected: int = 0
    threats_blocked: int = 0
    highest_severity: str | None = None
    scan_durations_ms: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_scan(
        self,
        scan_type: str,
        result: AgentScanResult,
        blocked: bool = False,
    ) -> None:
        """Record a scan for statistics (thread-safe).

        Args:
            scan_type: Type of scan (step, task, tool)
            result: AgentScanResult from scanner
            blocked: Whether execution was blocked
        """
        with self._lock:
            self.total_scans += 1
            self.scan_durations_ms.append(result.duration_ms)

            if scan_type == "step":
                self.step_scans += 1
            elif scan_type == "task":
                self.task_scans += 1
            elif scan_type == "tool":
                self.tool_scans += 1

            if result.has_threats:
                self.threats_detected += 1
                severity = result.severity
                if severity:
                    self._update_highest_severity(severity)

            if blocked:
                self.threats_blocked += 1

    def _update_highest_severity(self, severity: str) -> None:
        """Update highest severity seen (must be called with lock held)."""
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        current_level = severity_order.get(self.highest_severity or "", 0)
        new_level = severity_order.get(severity, 0)
        if new_level > current_level:
            self.highest_severity = severity

    @property
    def average_scan_duration_ms(self) -> float:
        """Calculate average scan duration (thread-safe)."""
        with self._lock:
            if not self.scan_durations_ms:
                return 0.0
            return sum(self.scan_durations_ms) / len(self.scan_durations_ms)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (thread-safe)."""
        with self._lock:
            return {
                "total_scans": self.total_scans,
                "step_scans": self.step_scans,
                "task_scans": self.task_scans,
                "tool_scans": self.tool_scans,
                "threats_detected": self.threats_detected,
                "threats_blocked": self.threats_blocked,
                "highest_severity": self.highest_severity,
                "average_scan_duration_ms": (
                    sum(self.scan_durations_ms) / len(self.scan_durations_ms)
                    if self.scan_durations_ms
                    else 0.0
                ),
            }


class RaxeCrewGuard:
    """Security guard for CrewAI multi-agent applications.

    RaxeCrewGuard provides automatic security scanning for CrewAI crews
    using the composition pattern. It can be used in several ways:

    1. **Callback Mode**: Pass callbacks to Crew constructor
    2. **Wrapper Mode**: Wrap a Crew for automatic protection
    3. **Manual Mode**: Call scan methods directly

    The guard uses the AgentScanner base class for core scanning logic
    and adds CrewAI-specific integration code.

    Attributes:
        raxe: RAXE client instance
        config: Guard configuration
        scanner: Underlying AgentScanner
        stats: Scan statistics for current/last crew run

    Example (Callback Mode):
        >>> from crewai import Crew, Agent, Task
        >>> from raxe import Raxe
        >>> from raxe.sdk.integrations import RaxeCrewGuard
        >>>
        >>> guard = RaxeCrewGuard(Raxe())
        >>>
        >>> crew = Crew(
        ...     agents=[researcher, writer],
        ...     tasks=[research_task, write_task],
        ...     step_callback=guard.step_callback,
        ...     task_callback=guard.task_callback,
        ... )
        >>>
        >>> result = crew.kickoff()
        >>> print(f"Threats detected: {guard.stats.threats_detected}")

    Example (Wrapper Mode):
        >>> guard = RaxeCrewGuard(Raxe())
        >>> protected_crew = guard.protect_crew(crew)
        >>> result = protected_crew.kickoff()

    Example (Strict Mode):
        >>> from raxe.sdk.integrations.agent_scanner import ScanMode
        >>>
        >>> config = CrewGuardConfig(
        ...     mode=ScanMode.BLOCK_ON_HIGH,
        ...     wrap_tools=True,
        ... )
        >>> guard = RaxeCrewGuard(Raxe(), config)
    """

    def __init__(
        self,
        raxe: Raxe,
        config: CrewGuardConfig | None = None,
    ) -> None:
        """Initialize CrewAI guard.

        Args:
            raxe: RAXE client instance for scanning
            config: Optional guard configuration
        """
        self._raxe = raxe
        self._config = config or CrewGuardConfig()
        self._scanner = create_agent_scanner(
            raxe, self._config.to_agent_scanner_config(), integration_type="crewai"
        )
        self._stats = CrewScanStats()

        logger.debug(
            "RaxeCrewGuard initialized",
            extra={
                "mode": self._config.mode.value,
                "wrap_tools": self._config.wrap_tools,
            },
        )

    @property
    def raxe(self) -> Raxe:
        """Get the RAXE client instance."""
        return self._raxe

    @property
    def config(self) -> CrewGuardConfig:
        """Get the guard configuration."""
        return self._config

    @property
    def scanner(self) -> AgentScanner:
        """Get the underlying AgentScanner."""
        return self._scanner

    @property
    def stats(self) -> CrewScanStats:
        """Get scan statistics for current/last crew run."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset scan statistics (call before new crew run)."""
        self._stats = CrewScanStats()

    def _raise_security_exception(self, result: AgentScanResult) -> None:
        """Raise SecurityException from an AgentScanResult.

        Handles both cases where pipeline_result is available or not.

        Args:
            result: AgentScanResult with threat details

        Raises:
            SecurityException: Always raises with appropriate error info
        """
        from raxe.sdk.exceptions import security_threat_detected_error

        if result.pipeline_result is not None:
            raise SecurityException(result.pipeline_result)

        # Create exception from AgentScanResult data
        error = security_threat_detected_error(
            severity=str(result.severity or "UNKNOWN"),
            detection_count=result.detection_count,
        )
        message = (
            f"Security threat detected: {result.severity} ({result.detection_count} detection(s))"
        )
        exc = SecurityException.__new__(SecurityException)
        exc.result = None
        exc.error = error
        Exception.__init__(exc, message)
        raise exc

    def step_callback(self, step_output: Any) -> None:
        """Callback for CrewAI step events.

        This callback is called after each agent step (thought-action-observation).
        Register with Crew(step_callback=guard.step_callback).

        Args:
            step_output: Step output from CrewAI (varies by version)
                Can be AgentAction, ToolResult, or string output

        Example:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                step_callback=guard.step_callback,
            )
        """
        if not self._config.scan_step_outputs:
            return

        try:
            # Extract text from step output
            text = self._extract_step_text(step_output)
            if not text:
                return

            # Extract agent info if available
            agent_name = self._extract_agent_name(step_output)

            # Create scan context
            context = ScanContext(
                message_type=MessageType.AGENT_TO_AGENT,
                sender_name=agent_name,
                metadata={
                    "source": "step_callback",
                    "step_type": type(step_output).__name__,
                },
            )

            # Perform scan
            result = self._scanner.scan_message(text, context=context)

            # Record stats
            self._stats.record_scan("step", result, result.should_block)

            # Handle blocking if configured
            if result.should_block:
                logger.warning(
                    "crew_step_blocked",
                    extra={
                        "agent": agent_name,
                        "severity": result.severity,
                        "prompt_hash": result.prompt_hash,
                    },
                )
                # Note: CrewAI step_callback doesn't support blocking
                # The threat is logged for monitoring

        except Exception as e:
            # Never fail the crew due to scanning errors
            logger.error(
                "crew_step_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    def task_callback(self, task_output: Any) -> None:
        """Callback for CrewAI task completion events.

        This callback is called after each task completes.
        Register with Crew(task_callback=guard.task_callback).

        Args:
            task_output: TaskOutput from CrewAI with task description and result

        Example:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                task_callback=guard.task_callback,
            )
        """
        if not self._config.scan_task_outputs:
            return

        try:
            # Extract text from task output
            text = self._extract_task_text(task_output)
            if not text:
                return

            # Extract task info
            task_description = self._extract_task_description(task_output)
            agent_name = self._extract_agent_from_task(task_output)

            # Create scan context
            context = ScanContext(
                message_type=MessageType.AGENT_RESPONSE,
                sender_name=agent_name,
                metadata={
                    "source": "task_callback",
                    "task_description": (task_description[:200] if task_description else None),
                },
            )

            # Perform scan
            result = self._scanner.scan_message(text, context=context)

            # Record stats
            self._stats.record_scan("task", result, result.should_block)

            # Handle blocking if configured
            if result.should_block:
                logger.warning(
                    "crew_task_blocked",
                    extra={
                        "agent": agent_name,
                        "severity": result.severity,
                        "task": task_description[:100] if task_description else None,
                        "prompt_hash": result.prompt_hash,
                    },
                )
                # Note: CrewAI task_callback doesn't support blocking
                # The threat is logged for monitoring

        except Exception as e:
            # Never fail the crew due to scanning errors
            logger.error(
                "crew_task_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    def before_kickoff(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Callback for before crew kickoff.

        Scan inputs before crew execution begins.
        Use with Crew @before_kickoff decorator or before_kickoff callback.

        Args:
            inputs: Input dictionary to the crew

        Returns:
            Original inputs (or modified if implementing input sanitization)

        Raises:
            SecurityException: If blocking mode and threat detected

        Example:
            @CrewBase
            class MyCrew:
                @before_kickoff
                def check_inputs(self, inputs):
                    return guard.before_kickoff(inputs)
        """
        if not self._config.scan_crew_inputs:
            return inputs

        # Reset stats for new run
        self.reset_stats()

        try:
            # Scan all string inputs
            for key, value in inputs.items():
                if isinstance(value, str) and value.strip():
                    context = ScanContext(
                        message_type=MessageType.HUMAN_INPUT,
                        metadata={
                            "source": "before_kickoff",
                            "input_key": key,
                        },
                    )

                    result = self._scanner.scan_message(value, context=context)

                    if result.should_block:
                        logger.warning(
                            "crew_input_blocked",
                            extra={
                                "input_key": key,
                                "severity": result.severity,
                                "prompt_hash": result.prompt_hash,
                            },
                        )
                        self._raise_security_exception(result)

        except (SecurityException, ThreatDetectedError):
            raise
        except Exception as e:
            logger.error(
                "crew_input_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        return inputs

    def after_kickoff(self, output: Any) -> Any:
        """Callback for after crew kickoff completes.

        Scan final crew output.
        Use with Crew @after_kickoff decorator or after_kickoff callback.

        Args:
            output: Final output from the crew

        Returns:
            Original output

        Example:
            @CrewBase
            class MyCrew:
                @after_kickoff
                def check_output(self, output):
                    return guard.after_kickoff(output)
        """
        if not self._config.scan_crew_outputs:
            return output

        try:
            # Extract text from output
            text = self._extract_crew_output_text(output)
            if text:
                context = ScanContext(
                    message_type=MessageType.AGENT_RESPONSE,
                    metadata={"source": "after_kickoff"},
                )

                result = self._scanner.scan_message(text, context=context)

                if result.has_threats:
                    logger.warning(
                        "crew_output_threat",
                        extra={
                            "severity": result.severity,
                            "prompt_hash": result.prompt_hash,
                        },
                    )

        except Exception as e:
            logger.error(
                "crew_output_scan_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        return output

    def protect_crew(self, crew: CrewType) -> CrewType:
        """Wrap a Crew with automatic security scanning.

        This method returns a proxy that automatically applies scanning
        to all crew operations.

        Args:
            crew: CrewAI Crew instance to protect

        Returns:
            Protected Crew instance with scanning enabled

        Example:
            >>> from crewai import Crew
            >>> crew = Crew(agents=[...], tasks=[...])
            >>> protected_crew = guard.protect_crew(crew)
            >>> result = protected_crew.kickoff()
        """
        # Store original callbacks
        original_step_callback = getattr(crew, "step_callback", None)
        original_task_callback = getattr(crew, "task_callback", None)

        # Combine with guard callbacks
        def combined_step_callback(step_output: Any) -> None:
            self.step_callback(step_output)
            if original_step_callback:
                original_step_callback(step_output)

        def combined_task_callback(task_output: Any) -> None:
            self.task_callback(task_output)
            if original_task_callback:
                original_task_callback(task_output)

        # Set combined callbacks
        crew.step_callback = combined_step_callback
        crew.task_callback = combined_task_callback

        # Optionally wrap tools
        if self._config.wrap_tools:
            self._wrap_crew_tools(crew)

        logger.debug(
            "crew_protected",
            extra={
                "mode": self._config.mode.value,
                "wrap_tools": self._config.wrap_tools,
            },
        )

        return crew

    def wrap_tool(self, tool: T) -> T:
        """Wrap a CrewAI tool with input/output scanning.

        Use this to protect individual tools. For automatic wrapping
        of all crew tools, use protect_crew() with wrap_tools=True.

        Args:
            tool: CrewAI BaseTool instance

        Returns:
            Wrapped tool with scanning enabled

        Example:
            >>> from crewai_tools import SerperDevTool
            >>> search_tool = guard.wrap_tool(SerperDevTool())
            >>> agent = Agent(tools=[search_tool])
        """
        # Get the original _run method
        original_run = getattr(tool, "_run", None)
        if original_run is None:
            logger.warning(
                "tool_wrap_failed",
                extra={"reason": "no _run method", "tool": type(tool).__name__},
            )
            return tool

        @functools.wraps(original_run)
        def wrapped_run(*args: Any, **kwargs: Any) -> Any:
            # Scan inputs
            if self._config.scan_tool_inputs:
                input_text = self._extract_tool_input(args, kwargs)
                if input_text:
                    self._scan_tool_io(
                        text=input_text,
                        tool_name=getattr(tool, "name", type(tool).__name__),
                        io_type="input",
                    )

            # Execute original
            result = original_run(*args, **kwargs)

            # Scan outputs
            if self._config.scan_tool_outputs:
                output_text = str(result) if result else None
                if output_text:
                    self._scan_tool_io(
                        text=output_text,
                        tool_name=getattr(tool, "name", type(tool).__name__),
                        io_type="output",
                    )

            return result

        # Replace _run method
        tool._run = wrapped_run

        logger.debug(
            "tool_wrapped",
            extra={"tool": getattr(tool, "name", type(tool).__name__)},
        )

        return tool

    def wrap_tools(self, tools: list[T]) -> list[T]:
        """Wrap multiple CrewAI tools with input/output scanning.

        Convenience method to wrap multiple tools at once.

        Args:
            tools: List of CrewAI BaseTool instances

        Returns:
            List of wrapped tools with scanning enabled

        Example:
            >>> from crewai_tools import SerperDevTool, FileReadTool
            >>> tools = [SerperDevTool(), FileReadTool()]
            >>> wrapped_tools = guard.wrap_tools(tools)
            >>> agent = Agent(tools=wrapped_tools)
        """
        return [self.wrap_tool(tool) for tool in tools]

    def _scan_tool_io(
        self,
        text: str,
        tool_name: str,
        io_type: str,
    ) -> None:
        """Scan tool input or output.

        Args:
            text: Text to scan
            tool_name: Name of the tool
            io_type: "input" or "output"
        """
        try:
            message_type = (
                MessageType.FUNCTION_CALL if io_type == "input" else MessageType.FUNCTION_RESULT
            )

            context = ScanContext(
                message_type=message_type,
                metadata={
                    "source": f"tool_{io_type}",
                    "tool_name": tool_name,
                },
            )

            result = self._scanner.scan_message(text, context=context)

            # Record stats
            self._stats.record_scan("tool", result, result.should_block)

            if result.has_threats:
                logger.warning(
                    f"crew_tool_{io_type}_threat",
                    extra={
                        "tool": tool_name,
                        "severity": result.severity,
                        "prompt_hash": result.prompt_hash,
                    },
                )

                # Block if configured
                if result.should_block:
                    self._raise_security_exception(result)

        except SecurityException:
            raise
        except Exception as e:
            logger.error(
                f"crew_tool_{io_type}_scan_error",
                extra={
                    "tool": tool_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    def _wrap_crew_tools(self, crew: Any) -> None:
        """Wrap all tools in a crew's agents.

        Args:
            crew: CrewAI Crew instance
        """
        agents = getattr(crew, "agents", [])
        for agent in agents:
            tools = getattr(agent, "tools", [])
            wrapped_tools = [self.wrap_tool(tool) for tool in tools]
            agent.tools = wrapped_tools

    def _extract_step_text(self, step_output: Any) -> str | None:
        """Extract text from step output.

        Uses unified extractors where applicable, with CrewAI-specific fallbacks.

        Args:
            step_output: Step output from CrewAI

        Returns:
            Text content or None
        """
        if isinstance(step_output, str):
            return step_output

        # Handle AgentAction
        if hasattr(step_output, "tool_input"):
            return str(step_output.tool_input)

        # Handle ToolResult
        if hasattr(step_output, "result"):
            return str(step_output.result)

        # Handle dict using unified extractor
        if isinstance(step_output, dict):
            return extract_text_from_dict(step_output, ("output", "text", "result"))

        # Handle thought attribute
        if hasattr(step_output, "thought"):
            return str(step_output.thought)

        # Handle log attribute
        if hasattr(step_output, "log"):
            return str(step_output.log)

        # Fallback to string conversion
        try:
            text = str(step_output)
            if text and len(text) < 10000:  # Sanity check
                return text
        except Exception:
            pass

        return None

    def _extract_task_text(self, task_output: Any) -> str | None:
        """Extract text from task output.

        Uses unified extractors where applicable, with CrewAI-specific fallbacks.

        Args:
            task_output: TaskOutput from CrewAI

        Returns:
            Text content or None
        """
        if isinstance(task_output, str):
            return task_output

        # Handle TaskOutput object
        if hasattr(task_output, "raw"):
            return str(task_output.raw)

        if hasattr(task_output, "output"):
            return str(task_output.output)

        if hasattr(task_output, "result"):
            return str(task_output.result)

        # Handle dict using unified extractor
        if isinstance(task_output, dict):
            return extract_text_from_dict(task_output, ("raw", "output", "result", "text"))

        return None

    def _extract_task_description(self, task_output: Any) -> str | None:
        """Extract task description from task output.

        Args:
            task_output: TaskOutput from CrewAI

        Returns:
            Task description or None
        """
        if hasattr(task_output, "description"):
            return str(task_output.description)

        if hasattr(task_output, "task") and hasattr(task_output.task, "description"):
            return str(task_output.task.description)

        if isinstance(task_output, dict) and "description" in task_output:
            return str(task_output["description"])

        return None

    def _extract_agent_name(self, step_output: Any) -> str | None:
        """Extract agent name from step output.

        Args:
            step_output: Step output from CrewAI

        Returns:
            Agent name or None
        """
        # Try direct agent attribute
        if hasattr(step_output, "agent"):
            agent = step_output.agent
            if hasattr(agent, "role"):
                return str(agent.role)
            if hasattr(agent, "name"):
                return str(agent.name)
            return str(agent)

        # Try agent_name attribute
        if hasattr(step_output, "agent_name"):
            return str(step_output.agent_name)

        # Try dict
        if isinstance(step_output, dict):
            if "agent" in step_output:
                return str(step_output["agent"])
            if "agent_name" in step_output:
                return str(step_output["agent_name"])

        return None

    def _extract_agent_from_task(self, task_output: Any) -> str | None:
        """Extract agent name from task output.

        Args:
            task_output: TaskOutput from CrewAI

        Returns:
            Agent name or None
        """
        if hasattr(task_output, "agent"):
            agent = task_output.agent
            if hasattr(agent, "role"):
                return str(agent.role)
            if hasattr(agent, "name"):
                return str(agent.name)

        if hasattr(task_output, "task") and hasattr(task_output.task, "agent"):
            agent = task_output.task.agent
            if hasattr(agent, "role"):
                return str(agent.role)

        return None

    def _extract_crew_output_text(self, output: Any) -> str | None:
        """Extract text from crew output.

        Uses unified extractors where applicable, with CrewAI-specific fallbacks.

        Args:
            output: CrewOutput from CrewAI

        Returns:
            Text content or None
        """
        if isinstance(output, str):
            return output

        # Handle CrewOutput
        if hasattr(output, "raw"):
            return str(output.raw)

        if hasattr(output, "result"):
            return str(output.result)

        # Handle dict using unified extractor
        if isinstance(output, dict):
            return extract_text_from_dict(output, ("raw", "result", "output", "text"))

        return None

    def _extract_tool_input(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str | None:
        """Extract tool input text from arguments.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Input text or None
        """
        # Check kwargs for common input keys
        for key in ["query", "input", "text", "question", "prompt"]:
            if key in kwargs:
                return str(kwargs[key])

        # Check first string arg
        for arg in args:
            if isinstance(arg, str):
                return arg

        # Fallback to all kwargs as string
        if kwargs:
            return str(kwargs)

        return None

    def get_summary(self) -> dict[str, Any]:
        """Get summary of guard activity.

        Returns:
            Dictionary with configuration and statistics
        """
        return {
            "config": {
                "mode": self._config.mode.value,
                "wrap_tools": self._config.wrap_tools,
                "scan_step_outputs": self._config.scan_step_outputs,
                "scan_task_outputs": self._config.scan_task_outputs,
            },
            "stats": self._stats.to_dict(),
        }

    # =========================================================================
    # Async Callback Methods
    # =========================================================================
    # Async versions of callbacks for use in async contexts.

    async def step_callback_async(self, step_output: Any) -> None:
        """Async callback for CrewAI step events.

        Async version of step_callback for use in async contexts.
        Uses asyncio.get_event_loop().run_in_executor() for non-blocking scans.

        Args:
            step_output: Step output from CrewAI
        """
        import asyncio

        if not self._config.scan_step_outputs:
            return

        try:
            text = self._extract_step_text(step_output)
            if not text:
                return

            agent_name = self._extract_agent_name(step_output)

            context = ScanContext(
                message_type=MessageType.AGENT_TO_AGENT,
                sender_name=agent_name,
                metadata={
                    "source": "step_callback_async",
                    "step_type": type(step_output).__name__,
                },
            )

            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._scanner.scan_message(text, context=context)
            )

            self._stats.record_scan("step", result, result.should_block)

            if result.should_block:
                logger.warning(
                    "crew_step_blocked_async",
                    extra={
                        "agent": agent_name,
                        "severity": result.severity,
                        "prompt_hash": result.prompt_hash,
                    },
                )

        except Exception as e:
            logger.error(
                "crew_step_scan_error_async",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    async def task_callback_async(self, task_output: Any) -> None:
        """Async callback for CrewAI task completion events.

        Async version of task_callback for use in async contexts.

        Args:
            task_output: TaskOutput from CrewAI
        """
        import asyncio

        if not self._config.scan_task_outputs:
            return

        try:
            text = self._extract_task_text(task_output)
            if not text:
                return

            task_description = self._extract_task_description(task_output)
            agent_name = self._extract_agent_from_task(task_output)

            context = ScanContext(
                message_type=MessageType.AGENT_RESPONSE,
                sender_name=agent_name,
                metadata={
                    "source": "task_callback_async",
                    "task_description": (task_description[:200] if task_description else None),
                },
            )

            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._scanner.scan_message(text, context=context)
            )

            self._stats.record_scan("task", result, result.should_block)

            if result.should_block:
                logger.warning(
                    "crew_task_blocked_async",
                    extra={
                        "agent": agent_name,
                        "severity": result.severity,
                        "task": task_description[:100] if task_description else None,
                        "prompt_hash": result.prompt_hash,
                    },
                )

        except Exception as e:
            logger.error(
                "crew_task_scan_error_async",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

    async def before_kickoff_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Async callback for before crew kickoff.

        Async version of before_kickoff for use in async contexts.

        Args:
            inputs: Input dictionary to the crew

        Returns:
            Original inputs

        Raises:
            SecurityException: If blocking mode and threat detected
        """
        import asyncio

        if not self._config.scan_crew_inputs:
            return inputs

        self.reset_stats()

        try:
            for key, value in inputs.items():
                if isinstance(value, str) and value.strip():
                    context = ScanContext(
                        message_type=MessageType.HUMAN_INPUT,
                        metadata={
                            "source": "before_kickoff_async",
                            "input_key": key,
                        },
                    )

                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda v=value: self._scanner.scan_message(v, context=context)
                    )

                    if result.should_block:
                        logger.warning(
                            "crew_input_blocked_async",
                            extra={
                                "input_key": key,
                                "severity": result.severity,
                                "prompt_hash": result.prompt_hash,
                            },
                        )
                        self._raise_security_exception(result)

        except (SecurityException, ThreatDetectedError):
            raise
        except Exception as e:
            logger.error(
                "crew_input_scan_error_async",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        return inputs

    async def after_kickoff_async(self, output: Any) -> Any:
        """Async callback for after crew kickoff completes.

        Async version of after_kickoff for use in async contexts.

        Args:
            output: Final output from the crew

        Returns:
            Original output
        """
        import asyncio

        if not self._config.scan_crew_outputs:
            return output

        try:
            text = self._extract_crew_output_text(output)
            if text:
                context = ScanContext(
                    message_type=MessageType.AGENT_RESPONSE,
                    metadata={"source": "after_kickoff_async"},
                )

                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._scanner.scan_message(text, context=context)
                )

                if result.has_threats:
                    logger.warning(
                        "crew_output_threat_async",
                        extra={
                            "severity": result.severity,
                            "prompt_hash": result.prompt_hash,
                        },
                    )

        except Exception as e:
            logger.error(
                "crew_output_scan_error_async",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        return output

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RaxeCrewGuard("
            f"mode={self._config.mode.value}, "
            f"scans={self._stats.total_scans}, "
            f"threats={self._stats.threats_detected})"
        )


# Convenience function for quick setup
def create_crew_guard(
    raxe: Raxe | None = None,
    mode: ScanMode = ScanMode.LOG_ONLY,
    **kwargs: Any,
) -> RaxeCrewGuard:
    """Create a RaxeCrewGuard with common defaults.

    Convenience function for quick guard creation.

    Args:
        raxe: Optional RAXE client (creates default if None)
        mode: Scan mode (default: LOG_ONLY)
        **kwargs: Additional CrewGuardConfig parameters

    Returns:
        Configured RaxeCrewGuard instance

    Example:
        >>> from raxe.sdk.integrations import create_crew_guard
        >>> from raxe.sdk.integrations.agent_scanner import ScanMode
        >>>
        >>> # Quick monitoring setup
        >>> guard = create_crew_guard()
        >>>
        >>> # Strict mode
        >>> guard = create_crew_guard(mode=ScanMode.BLOCK_ON_HIGH)
    """
    from raxe.sdk.client import Raxe

    if raxe is None:
        raxe = Raxe()

    config = CrewGuardConfig(mode=mode, **kwargs)
    return RaxeCrewGuard(raxe, config)


__all__ = [
    "CrewGuardConfig",
    "CrewScanStats",
    "RaxeCrewGuard",
    "create_crew_guard",
]
