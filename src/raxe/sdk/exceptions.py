"""RAXE SDK exceptions.

Custom exception hierarchy for RAXE SDK operations.
All RAXE exceptions inherit from RaxeException for easy catching.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult


class RaxeException(Exception):
    """Base exception for all RAXE errors."""

    pass


class SecurityException(RaxeException):
    """Raised when a security threat is detected and blocking is enabled.

    This exception is raised when:
    - A threat is detected during scanning
    - The policy dictates blocking (e.g., CRITICAL severity)
    - block_on_threat=True is specified

    Attributes:
        result: The ScanPipelineResult that triggered the exception
    """

    def __init__(self, result: "ScanPipelineResult") -> None:
        """Initialize security exception.

        Args:
            result: ScanPipelineResult containing threat details
        """
        self.result = result
        super().__init__(
            f"Security threat detected: {result.severity} "
            f"({result.total_detections} detection(s))"
        )


class RaxeBlockedError(SecurityException):
    """Raised when a request is blocked by policy.

    This is a specialized SecurityException that indicates
    the request was explicitly blocked by policy evaluation.
    """

    def __init__(self, result: "ScanPipelineResult") -> None:
        """Initialize blocked error.

        Args:
            result: ScanPipelineResult with blocking decision
        """
        super().__init__(result)
        self.args = (
            f"Request blocked by policy: {result.policy_decision} "
            f"(Severity: {result.severity})",
        )
