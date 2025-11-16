"""File Logger Plugin.

Example action plugin that logs scan results to a file in JSON Lines format.
Useful for audit trails, debugging, and offline analysis.

Configuration (~/.raxe/config.toml):
    ```toml
    [plugins.file_logger]
    path = "~/.raxe/logs/scan.jsonl"  # Expanded automatically
    threats_only = false  # Log all scans, not just threats
    include_metadata = true
    rotate_size_mb = 100  # Rotate when file exceeds 100MB
    ```

Output Format:
    Each line is a JSON object:
    ```json
    {
        "timestamp": "2024-01-15T10:30:45.123Z",
        "has_threats": true,
        "severity": "HIGH",
        "total_detections": 3,
        "should_block": true,
        "policy_decision": "BLOCK",
        "duration_ms": 8.5,
        "text_hash": "abc123...",
        "detections": [...]
    }
    ```

Usage:
    1. Copy this directory to ~/.raxe/plugins/file_logger/
    2. Configure log path in config.toml
    3. Enable in plugins.enabled list
    4. Logs will be written to specified file
    5. Analyze with: cat ~/.raxe/logs/scan.jsonl | jq
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.plugins import ActionPlugin, PluginMetadata, PluginPriority


class FileLoggerPlugin(ActionPlugin):
    """Log scan results to JSON Lines file.

    Writes one JSON object per line to a log file. This format is:
    - Easy to parse with standard tools (jq, grep, etc.)
    - Streamable (can read line-by-line)
    - Compatible with log aggregation tools
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="file_logger",
            version="1.0.0",
            author="RAXE",
            description="Log scan results to JSON Lines file",
            priority=PluginPriority.LOW,
            requires=("raxe>=1.0.0",),
            tags=("action", "logging", "file", "audit"),
        )

    def on_init(self, config: dict[str, Any]) -> None:
        """Initialize with file logger configuration.

        Args:
            config: Plugin configuration from config.toml

        Raises:
            ValueError: If configuration is invalid
            IOError: If log file cannot be opened
        """
        # Get log path (expand ~ and environment variables)
        log_path_str = config.get("path", "~/.raxe/logs/scan.jsonl")
        self.log_path = Path(log_path_str).expanduser().resolve()

        # Create parent directory if needed
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.threats_only = config.get("threats_only", False)
        self.include_metadata = config.get("include_metadata", True)
        self.rotate_size_mb = config.get("rotate_size_mb", 100)

        # Open log file in append mode
        try:
            self.file_handle = open(self.log_path, "a", encoding="utf-8")
        except IOError as e:
            raise IOError(f"Cannot open log file {self.log_path}: {e}") from e

    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Determine if result should be logged.

        Args:
            result: Scan pipeline result

        Returns:
            True if should log
        """
        if self.threats_only:
            return result.has_threats
        return True

    def execute(self, result: ScanPipelineResult) -> None:
        """Log scan result to file.

        Args:
            result: Scan pipeline result
        """
        # Check if rotation needed
        self._check_rotation()

        # Build log entry
        log_entry = self._build_log_entry(result)

        # Write to file
        try:
            json.dump(log_entry, self.file_handle, ensure_ascii=False)
            self.file_handle.write("\n")
            self.file_handle.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to write log entry: {e}") from e

    def _build_log_entry(self, result: ScanPipelineResult) -> dict[str, Any]:
        """Build log entry from scan result.

        Args:
            result: Scan pipeline result

        Returns:
            JSON-serializable log entry
        """
        # Base entry
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_threats": result.has_threats,
            "severity": result.severity,
            "total_detections": result.total_detections,
            "should_block": result.should_block,
            "policy_decision": result.policy_decision.value,
            "duration_ms": result.duration_ms,
            "text_hash": result.text_hash,  # Privacy-preserving
        }

        # Add detections
        detections = []
        for detection in result.scan_result.l1_result.detections:
            detections.append(
                {
                    "rule_id": detection.rule_id,
                    "severity": detection.severity.name,
                    "confidence": detection.confidence,
                    "message": detection.message,
                }
            )
        entry["detections"] = detections

        # Add metadata if enabled
        if self.include_metadata:
            entry["metadata"] = result.metadata

        return entry

    def _check_rotation(self) -> None:
        """Check if log file needs rotation.

        Rotates file if it exceeds configured size limit.
        Rotated files are renamed with timestamp suffix.
        """
        try:
            # Get current file size
            if not self.log_path.exists():
                return

            size_mb = self.log_path.stat().st_size / (1024 * 1024)

            # Check if rotation needed
            if size_mb >= self.rotate_size_mb:
                # Close current file
                self.file_handle.close()

                # Rotate with timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                rotated_path = self.log_path.with_suffix(f".{timestamp}.jsonl")
                self.log_path.rename(rotated_path)

                # Open new file
                self.file_handle = open(self.log_path, "a", encoding="utf-8")

        except Exception as e:
            # Don't crash on rotation errors
            # Just log and continue with existing file
            raise RuntimeError(f"Log rotation failed: {e}") from e

    def on_shutdown(self) -> None:
        """Close log file on shutdown."""
        if hasattr(self, "file_handle") and not self.file_handle.closed:
            try:
                self.file_handle.close()
            except Exception:
                pass  # Ignore errors during shutdown


# Required: Export plugin instance
plugin = FileLoggerPlugin()
