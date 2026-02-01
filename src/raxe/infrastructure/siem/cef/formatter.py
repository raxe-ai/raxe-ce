"""CEF (Common Event Format) formatter.

Pure formatting logic for converting RAXE events to CEF format.
No I/O operations - this is domain-level formatting.

CEF Format:
    CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension

Example:
    CEF:0|RAXE|ThreatDetection|0.9.0|pi-001|Prompt Injection Detected|10|src=192.168.1.1

References:
    - ArcSight CEF Developer Guide
    - https://www.microfocus.com/documentation/arcsight/arcsight-smartconnectors-8.3/
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar


class CEFFormatter:
    """CEF message formatter.

    Converts RAXE telemetry events to CEF format. This class handles:
    - Character escaping (header and extension contexts differ)
    - Severity mapping (RAXE → CEF 0-10 → Syslog)
    - Header building (CEF:0|vendor|product|version|sig|name|sev|)
    - Extension building (key=value pairs)

    Thread-safe: No mutable state.

    Example:
        >>> formatter = CEFFormatter()
        >>> cef_message = formatter.format_event(raxe_event)
        >>> print(cef_message)
        CEF:0|RAXE|ThreatDetection|0.9.0|pi-001|Threat Detected|10|...
    """

    # CEF severity mapping from RAXE severity levels
    SEVERITY_MAP: ClassVar[dict[str, int]] = {
        "none": 0,
        "low": 3,
        "medium": 5,
        "high": 7,
        "critical": 10,
    }

    # CEF severity to syslog severity mapping
    # CEF 0-3 → informational/notice (5-6)
    # CEF 4-6 → warning (4)
    # CEF 7-8 → error (3)
    # CEF 9-10 → critical (2)
    CEF_TO_SYSLOG_MAP: ClassVar[dict[int, int]] = {
        0: 6,  # informational
        1: 6,  # informational
        2: 6,  # informational
        3: 5,  # notice
        4: 5,  # notice
        5: 4,  # warning
        6: 4,  # warning
        7: 3,  # error
        8: 3,  # error
        9: 2,  # critical
        10: 2,  # critical
    }

    # ArcSight category mapping for rule families
    FAMILY_TO_CATEGORY: ClassVar[dict[str, str]] = {
        "PI": "/Security/Attack/Injection",
        "JB": "/Security/Attack/Jailbreak",
        "MH": "/Security/Attack/ModelHijacking",
        "DE": "/Security/DataLoss/Exfiltration",
        "PL": "/Security/DataLoss/PIILeak",
        "HM": "/Security/Malware/Harmful",
        "EP": "/Security/Attack/ExcessivePermissions",
        "RV": "/Security/Manipulation/ResponseViolation",
        "SC": "/Security/Attack/SystemCompromise",
        "ENC": "/Security/Encoding/Evasion",
    }

    def __init__(
        self,
        device_vendor: str = "RAXE",
        device_product: str = "ThreatDetection",
        device_version: str | None = None,
    ) -> None:
        """Initialize CEF formatter.

        Args:
            device_vendor: CEF Device Vendor field (default: RAXE)
            device_product: CEF Device Product field (default: ThreatDetection)
            device_version: CEF Device Version field (default: RAXE version)
        """
        self.device_vendor = device_vendor
        self.device_product = device_product

        if device_version is None:
            try:
                from raxe import __version__

                device_version = __version__
            except ImportError:
                device_version = "0.0.0"
        self.device_version = device_version

    def _escape_header(self, value: str) -> str:
        """Escape special characters in CEF header context.

        In CEF headers, pipes (|) and backslashes (\\) must be escaped.

        Args:
            value: String to escape

        Returns:
            Escaped string safe for CEF header
        """
        if not value:
            return value
        # Order matters: escape backslashes first
        result = value.replace("\\", "\\\\")
        result = result.replace("|", "\\|")
        return result

    def _escape_extension(self, value: str) -> str:
        """Escape special characters in CEF extension context.

        In CEF extensions, equals (=), newlines, and backslashes must be escaped.

        Args:
            value: String to escape

        Returns:
            Escaped string safe for CEF extension values
        """
        if not value:
            return value
        # Order matters: escape backslashes first
        result = value.replace("\\", "\\\\")
        result = result.replace("=", "\\=")
        result = result.replace("\n", "\\n")
        result = result.replace("\r", "\\r")
        return result

    def map_severity(self, raxe_severity: str) -> int:
        """Map RAXE severity to CEF severity (0-10).

        Args:
            raxe_severity: RAXE severity (none, LOW, MEDIUM, HIGH, CRITICAL)

        Returns:
            CEF severity integer 0-10
        """
        return self.SEVERITY_MAP.get(raxe_severity.lower(), 0)

    def map_cef_to_syslog_severity(self, cef_severity: int) -> int:
        """Map CEF severity (0-10) to syslog severity (0-7).

        Syslog severities:
            0 = Emergency, 1 = Alert, 2 = Critical, 3 = Error,
            4 = Warning, 5 = Notice, 6 = Informational, 7 = Debug

        Args:
            cef_severity: CEF severity 0-10

        Returns:
            Syslog severity 0-7
        """
        return self.CEF_TO_SYSLOG_MAP.get(cef_severity, 6)

    def _build_header(
        self,
        signature_id: str,
        event_name: str,
        severity: int,
    ) -> str:
        """Build CEF header string.

        Format: CEF:0|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|

        Args:
            signature_id: Unique identifier for event type (e.g., rule_id)
            event_name: Human-readable event name
            severity: CEF severity (0-10)

        Returns:
            CEF header string ending with pipe
        """
        return (
            f"CEF:0|"
            f"{self._escape_header(self.device_vendor)}|"
            f"{self._escape_header(self.device_product)}|"
            f"{self._escape_header(self.device_version)}|"
            f"{self._escape_header(signature_id)}|"
            f"{self._escape_header(event_name)}|"
            f"{severity}|"
        )

    def _build_extension(self, fields: dict[str, Any]) -> str:
        """Build CEF extension string.

        Format: key1=value1 key2=value2

        Args:
            fields: Dictionary of extension fields (None values skipped)

        Returns:
            Space-separated key=value pairs
        """
        parts = []
        for key, value in fields.items():
            if value is None:
                continue
            escaped_value = self._escape_extension(str(value))
            parts.append(f"{key}={escaped_value}")
        return " ".join(parts)

    def _extract_signature_id(self, event: dict[str, Any]) -> str:
        """Extract signature ID from event.

        Uses first rule_id if available, otherwise event_type.

        Args:
            event: RAXE event

        Returns:
            Signature ID string
        """
        payload = event.get("payload", {})
        l1 = payload.get("l1", {})
        detections = l1.get("detections", [])

        if detections and detections[0].get("rule_id"):
            return str(detections[0]["rule_id"])

        return str(event.get("event_type", "unknown"))

    def _extract_event_name(self, event: dict[str, Any]) -> str:
        """Extract human-readable event name.

        Args:
            event: RAXE event

        Returns:
            Event name string
        """
        payload = event.get("payload", {})
        threat_detected = payload.get("threat_detected", False)
        l1 = payload.get("l1", {})
        families = l1.get("families", [])

        if threat_detected:
            family = families[0] if families else "Unknown"
            return f"{family} Threat Detected"
        return "Scan Completed"

    def _extract_severity(self, event: dict[str, Any]) -> int:
        """Extract and map severity from event.

        Args:
            event: RAXE event

        Returns:
            CEF severity 0-10
        """
        payload = event.get("payload", {})
        l1 = payload.get("l1", {})
        severity_str = l1.get("highest_severity", "none")
        return self.map_severity(severity_str)

    def _extract_timestamp_ms(self, event: dict[str, Any]) -> int:
        """Extract timestamp as milliseconds since epoch.

        Args:
            event: RAXE event

        Returns:
            Timestamp in milliseconds
        """
        timestamp_str = event.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            return int(datetime.now().timestamp() * 1000)

    def _get_arcsight_category(self, families: list[str]) -> str:
        """Get ArcSight category for rule families.

        Args:
            families: List of RAXE rule family codes

        Returns:
            ArcSight category path
        """
        if not families:
            return "/Security/Other"
        return self.FAMILY_TO_CATEGORY.get(families[0], "/Security/Other")

    def format_event(self, event: dict[str, Any]) -> str:
        """Format RAXE event as CEF message.

        Args:
            event: RAXE telemetry event (from TelemetryEvent.to_dict())

        Returns:
            Complete CEF message string
        """
        payload = event.get("payload", {})
        metadata = event.get("_metadata", {})
        l1 = payload.get("l1", {})

        # Extract header components
        signature_id = self._extract_signature_id(event)
        event_name = self._extract_event_name(event)
        severity = self._extract_severity(event)

        # Build header
        header = self._build_header(signature_id, event_name, severity)

        # Build extension fields using CEF standard field names
        # See: https://www.microfocus.com/documentation/arcsight/arcsight-smartconnectors-8.3/
        extension_fields: dict[str, Any] = {
            # Required/common fields
            "rt": self._extract_timestamp_ms(event),
            "src": metadata.get("installation_id"),
            "suser": payload.get("agent_id"),
            "msg": event_name,
            "act": payload.get("action_taken"),
            # Custom string fields (cs1-cs6)
            "cs1": payload.get("prompt_hash"),
            "cs1Label": "PromptHash",
            "cs2": ",".join(
                d.get("rule_id", "") for d in l1.get("detections", []) if d.get("rule_id")
            )
            or None,
            "cs2Label": "RuleIDs" if l1.get("detections") else None,
            "cs3": ",".join(l1.get("families", [])) or None,
            "cs3Label": "ThreatFamilies" if l1.get("families") else None,
            "cs4": event.get("event_id"),
            "cs4Label": "EventID",
            "cs5": payload.get("mssp_id"),
            "cs5Label": "MSSPId" if payload.get("mssp_id") else None,
            "cs6": payload.get("customer_id"),
            "cs6Label": "CustomerId" if payload.get("customer_id") else None,
            # Custom numeric fields (cn1-cn3)
            "cn1": payload.get("prompt_length"),
            "cn1Label": "PromptLength" if payload.get("prompt_length") else None,
            "cn2": payload.get("scan_duration_ms"),
            "cn2Label": "ScanDurationMs" if payload.get("scan_duration_ms") else None,
            "cn3": l1.get("detection_count"),
            "cn3Label": "DetectionCount" if l1.get("detection_count") else None,
            # Device info
            "dvcVersion": metadata.get("version"),
        }

        # Remove None labels
        extension_fields = {k: v for k, v in extension_fields.items() if v is not None}

        extension = self._build_extension(extension_fields)

        return header + extension
