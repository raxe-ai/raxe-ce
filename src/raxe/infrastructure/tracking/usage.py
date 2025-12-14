"""Installation and usage tracking for RAXE CE.

Tracks privacy-preserving metrics:
- Installation metadata (when, Python version, OS)
- Time to first scan (critical activation metric)
- Usage patterns (DAU/WAU/MAU)
- Feature adoption (CLI commands used)

All tracking is local-only, opt-in telemetry to cloud.
"""
import json
import platform
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class InstallationInfo:
    """Installation metadata.

    Attributes:
        installation_id: Unique installation UUID
        installed_at: When RAXE was installed (ISO 8601)
        python_version: Python version string
        os: Operating system (darwin, linux, windows)
        install_source: Where installed from (pypi, git, source)
        raxe_version: RAXE version installed
    """
    installation_id: str
    installed_at: str
    python_version: str
    os: str
    install_source: str = "pypi"
    raxe_version: str = "0.0.1"


@dataclass
class UsageStats:
    """Usage statistics.

    Attributes:
        first_scan_at: When first scan occurred (ISO 8601)
        time_to_first_scan_seconds: Time from install to first scan
        total_scans: Total number of scans performed
        scans_with_threats: Scans that found threats
        last_scan_at: When last scan occurred
        days_active: List of day offsets when scans occurred (for DAU/WAU/MAU)
        commands_used: Set of CLI commands used
        features_enabled: Set of features enabled (L2, telemetry, etc.)
    """
    first_scan_at: str | None = None
    time_to_first_scan_seconds: int | None = None
    total_scans: int = 0
    scans_with_threats: int = 0
    last_scan_at: str | None = None
    days_active: list[int] = field(default_factory=list)
    commands_used: list[str] = field(default_factory=list)
    features_enabled: list[str] = field(default_factory=list)


class UsageTracker:
    """Tracks installation and usage metrics locally.

    Files:
        ~/.raxe/install.json - Installation metadata
        ~/.raxe/usage.json - Usage statistics

    Privacy:
        - All tracking is local-only
        - No PII stored (prompts, responses, API keys)
        - Only aggregated metrics sent to cloud (if telemetry enabled)
    """

    def __init__(self, data_dir: Path | None = None):
        """Initialize usage tracker.

        Args:
            data_dir: Directory for tracking files (default: ~/.raxe)
        """
        if data_dir is None:
            data_dir = Path.home() / ".raxe"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.install_file = self.data_dir / "install.json"
        self.usage_file = self.data_dir / "usage.json"

        # Load or create installation info
        self._install_info = self._load_or_create_install_info()

        # Load or create usage stats
        self._usage_stats = self._load_or_create_usage_stats()

    def _load_or_create_install_info(self) -> InstallationInfo:
        """Load or create installation info.

        Returns:
            InstallationInfo instance
        """
        if self.install_file.exists():
            with open(self.install_file) as f:
                data = json.load(f)
                return InstallationInfo(**data)

        # Create new installation record
        from raxe import __version__

        install_info = InstallationInfo(
            installation_id=str(uuid.uuid4()),
            installed_at=datetime.now(timezone.utc).isoformat(),
            python_version=platform.python_version(),
            os=sys.platform,
            install_source=self._detect_install_source(),
            raxe_version=__version__,
        )

        # Save
        with open(self.install_file, "w") as f:
            json.dump(asdict(install_info), f, indent=2)

        return install_info

    def _detect_install_source(self) -> str:
        """Detect how RAXE was installed.

        Returns:
            Install source (pypi, git, source)
        """
        # Check if running from git repository
        try:
            import raxe
            raxe_path = Path(raxe.__file__).parent
            if (raxe_path.parent.parent / ".git").exists():
                return "git"
        except Exception:
            pass

        # Check if installed via pip
        try:
            import importlib.metadata
            dist = importlib.metadata.distribution("raxe")
            if dist:
                return "pypi"
        except Exception:
            pass

        return "source"

    def _load_or_create_usage_stats(self) -> UsageStats:
        """Load or create usage statistics.

        Returns:
            UsageStats instance
        """
        if self.usage_file.exists():
            with open(self.usage_file) as f:
                data = json.load(f)
                return UsageStats(**data)

        # Create new usage stats
        return UsageStats()

    def _save_usage_stats(self) -> None:
        """Save usage statistics to disk."""
        with open(self.usage_file, "w") as f:
            json.dump(asdict(self._usage_stats), f, indent=2)

    def record_first_scan(self) -> None:
        """Record the first scan (critical activation metric)."""
        if self._usage_stats.first_scan_at is not None:
            # Already recorded
            return

        now = datetime.now(timezone.utc)
        self._usage_stats.first_scan_at = now.isoformat()

        # Calculate time to first scan
        # Parse install time with timezone awareness
        install_time = datetime.fromisoformat(self._install_info.installed_at)
        # Ensure timezone awareness for both datetimes
        if install_time.tzinfo is None:
            install_time = install_time.replace(tzinfo=timezone.utc)

        time_to_first_scan = (now - install_time).total_seconds()
        self._usage_stats.time_to_first_scan_seconds = int(time_to_first_scan)

        self._save_usage_stats()

    def record_scan(self, found_threats: bool = False) -> None:
        """Record a scan event.

        Args:
            found_threats: Whether threats were found
        """
        # Ensure first scan is recorded
        if self._usage_stats.first_scan_at is None:
            self.record_first_scan()

        # Update counters
        self._usage_stats.total_scans += 1
        if found_threats:
            self._usage_stats.scans_with_threats += 1

        # Update last scan time
        now = datetime.now(timezone.utc)
        self._usage_stats.last_scan_at = now.isoformat()

        # Track active day (day offset from installation)
        install_date = datetime.fromisoformat(self._install_info.installed_at).date()
        today = now.date()
        day_offset = (today - install_date).days

        if day_offset not in self._usage_stats.days_active:
            self._usage_stats.days_active.append(day_offset)

        self._save_usage_stats()

    def record_command(self, command: str) -> None:
        """Record CLI command usage.

        Args:
            command: Command name (e.g., "scan", "init", "config")
        """
        if command not in self._usage_stats.commands_used:
            self._usage_stats.commands_used.append(command)
            self._save_usage_stats()

    def record_feature(self, feature: str) -> None:
        """Record feature enablement.

        Args:
            feature: Feature name (e.g., "l2_detection", "telemetry")
        """
        if feature not in self._usage_stats.features_enabled:
            self._usage_stats.features_enabled.append(feature)
            self._save_usage_stats()

    def get_install_info(self) -> InstallationInfo:
        """Get installation information.

        Returns:
            InstallationInfo instance
        """
        return self._install_info

    def get_usage_stats(self) -> UsageStats:
        """Get usage statistics.

        Returns:
            UsageStats instance
        """
        return self._usage_stats

    def get_dau(self) -> bool:
        """Check if user is a Daily Active User (scanned today).

        Returns:
            True if scanned today
        """
        if not self._usage_stats.last_scan_at:
            return False

        last_scan = datetime.fromisoformat(self._usage_stats.last_scan_at).date()
        today = datetime.now(timezone.utc).date()

        return last_scan == today

    def get_wau(self) -> bool:
        """Check if user is a Weekly Active User (scanned in last 7 days).

        Returns:
            True if scanned in last 7 days
        """
        if not self._usage_stats.last_scan_at:
            return False

        last_scan = datetime.fromisoformat(self._usage_stats.last_scan_at).date()
        today = datetime.now(timezone.utc).date()

        return (today - last_scan).days <= 7

    def get_mau(self) -> bool:
        """Check if user is a Monthly Active User (scanned in last 30 days).

        Returns:
            True if scanned in last 30 days
        """
        if not self._usage_stats.last_scan_at:
            return False

        last_scan = datetime.fromisoformat(self._usage_stats.last_scan_at).date()
        today = datetime.now(timezone.utc).date()

        return (today - last_scan).days <= 30

    def get_retention_metrics(self) -> dict[str, Any]:
        """Get retention metrics (7-day, 30-day).

        Returns:
            Dictionary with retention metrics
        """
        install_date = datetime.fromisoformat(self._install_info.installed_at).date()
        today = datetime.now(timezone.utc).date()
        days_since_install = (today - install_date).days

        # 7-day retention: Did they come back within 7 days?
        retention_7d = False
        if days_since_install >= 7:
            retention_7d = any(1 <= day <= 7 for day in self._usage_stats.days_active)

        # 30-day retention: Did they come back within 30 days?
        retention_30d = False
        if days_since_install >= 30:
            retention_30d = any(1 <= day <= 30 for day in self._usage_stats.days_active)

        return {
            "days_since_install": days_since_install,
            "retention_7d": retention_7d,
            "retention_30d": retention_30d,
            "total_active_days": len(self._usage_stats.days_active),
            "dau": self.get_dau(),
            "wau": self.get_wau(),
            "mau": self.get_mau(),
        }

    def get_activation_metrics(self) -> dict[str, Any]:
        """Get activation metrics (time to first scan, engagement).

        Returns:
            Dictionary with activation metrics
        """
        return {
            "installed_at": self._install_info.installed_at,
            "first_scan_at": self._usage_stats.first_scan_at,
            "time_to_first_scan_seconds": self._usage_stats.time_to_first_scan_seconds,
            "time_to_first_scan_minutes": (
                self._usage_stats.time_to_first_scan_seconds / 60
                if self._usage_stats.time_to_first_scan_seconds
                else None
            ),
            "total_scans": self._usage_stats.total_scans,
            "scans_with_threats": self._usage_stats.scans_with_threats,
            "threat_detection_rate": (
                self._usage_stats.scans_with_threats / self._usage_stats.total_scans
                if self._usage_stats.total_scans > 0
                else 0
            ),
        }

    def export_for_telemetry(self) -> dict[str, Any]:
        """Export privacy-safe metrics for telemetry.

        Only includes aggregated, non-PII metrics.

        Returns:
            Dictionary safe for telemetry transmission
        """
        return {
            "installation_id": self._install_info.installation_id,
            "python_version": self._install_info.python_version,
            "os": self._install_info.os,
            "raxe_version": self._install_info.raxe_version,
            "install_source": self._install_info.install_source,
            "activation": self.get_activation_metrics(),
            "retention": self.get_retention_metrics(),
            "commands_used": self._usage_stats.commands_used,
            "features_enabled": self._usage_stats.features_enabled,
        }


# Global singleton instance
_tracker: UsageTracker | None = None


def get_tracker() -> UsageTracker:
    """Get global usage tracker instance.

    Returns:
        UsageTracker singleton
    """
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
