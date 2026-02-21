"""
Agent Registry for MSSP ecosystem.

Stores and tracks agent information based on heartbeats.
Provides agent status (online/offline/degraded) based on heartbeat timing.

Storage: File-based JSON in ~/.raxe/agents/registry.json
"""

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AgentRecord:
    """Record of a registered agent.

    Attributes:
        agent_id: Unique agent identifier
        mssp_id: MSSP/Partner identifier
        customer_id: Customer identifier
        version: Agent/RAXE version
        platform: OS platform (darwin, linux, win32)
        integration: Integration type (langchain, crewai, etc.)
        first_seen: ISO8601 timestamp of first heartbeat
        last_heartbeat: ISO8601 timestamp of last heartbeat
        uptime_seconds: Uptime at last heartbeat
        scans_total: Total scans reported
        threats_total: Total threats reported
        last_known_status: Last computed status for change detection
    """

    agent_id: str
    mssp_id: str
    customer_id: str
    version: str = ""
    platform: str = ""
    integration: str | None = None
    first_seen: str = ""
    last_heartbeat: str = ""
    uptime_seconds: float = 0.0
    scans_total: int = 0
    threats_total: int = 0
    last_known_status: str = "unknown"


@dataclass
class AgentRegistryConfig:
    """Configuration for agent registry.

    Attributes:
        registry_path: Path to registry JSON file
        online_threshold_seconds: Max seconds since heartbeat for "online" status
        degraded_threshold_seconds: Max seconds since heartbeat for "degraded" status
    """

    registry_path: str = field(default_factory=lambda: "~/.raxe/agents/registry.json")
    online_threshold_seconds: int = 120  # 2 minutes
    degraded_threshold_seconds: int = 300  # 5 minutes


class AgentRegistry:
    """Registry for tracking agents via heartbeats.

    Provides:
    - Registration of agents on heartbeat
    - Agent listing by MSSP/customer
    - Status calculation based on heartbeat timing

    Example:
        >>> registry = AgentRegistry()
        >>> registry.register_heartbeat(
        ...     agent_id="agent_xyz",
        ...     mssp_id="mssp_partner",
        ...     customer_id="cust_acme",
        ...     version="0.9.0",
        ...     platform="darwin",
        ...     uptime_seconds=3600,
        ...     scans=100,
        ...     threats=5,
        ... )
        >>> agents = registry.list_agents(mssp_id="mssp_partner")
    """

    def __init__(self, config: AgentRegistryConfig | None = None) -> None:
        """Initialize agent registry.

        Args:
            config: Registry configuration
        """
        self.config = config or AgentRegistryConfig()
        self._lock = threading.Lock()
        self._agents: dict[str, AgentRecord] = {}
        self._ensure_directory()
        self._load()

    def _ensure_directory(self) -> None:
        """Create registry directory if it doesn't exist."""
        registry_path = Path(self.config.registry_path).expanduser()
        registry_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load registry from file."""
        registry_path = Path(self.config.registry_path).expanduser()

        if not registry_path.exists():
            return

        try:
            with open(registry_path) as f:
                data = json.load(f)

            for agent_data in data.get("agents", []):
                record = AgentRecord(**agent_data)
                self._agents[record.agent_id] = record
        except Exception:
            # Start fresh if file is corrupted
            self._agents = {}

    def _save(self) -> None:
        """Save registry to file."""
        registry_path = Path(self.config.registry_path).expanduser()

        data = {
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "agents": [asdict(a) for a in self._agents.values()],
        }

        with open(registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register_heartbeat(
        self,
        agent_id: str,
        mssp_id: str,
        customer_id: str,
        version: str = "",
        platform: str = "",
        integration: str | None = None,
        uptime_seconds: float = 0.0,
        scans: int = 0,
        threats: int = 0,
    ) -> dict[str, Any] | None:
        """Register or update an agent from heartbeat.

        Args:
            agent_id: Agent identifier
            mssp_id: MSSP identifier
            customer_id: Customer identifier
            version: RAXE version
            platform: OS platform
            integration: Integration type
            uptime_seconds: Uptime at heartbeat
            scans: Scans since last heartbeat
            threats: Threats since last heartbeat

        Returns:
            Status change dict if status changed, None otherwise.
            Dict contains: previous_status, new_status, reason
        """
        now = datetime.now(timezone.utc).isoformat()
        status_change: dict[str, Any] | None = None

        with self._lock:
            if agent_id in self._agents:
                # Update existing
                record = self._agents[agent_id]
                previous_status = record.last_known_status

                # Compute what the status was before this heartbeat
                if previous_status in ("offline", "degraded", "unknown"):
                    # Agent came back online
                    status_change = {
                        "agent_id": agent_id,
                        "mssp_id": mssp_id,
                        "customer_id": customer_id,
                        "previous_status": previous_status,
                        "new_status": "online",
                        "reason": "heartbeat_received",
                        "agent_version": version or record.version,
                        "platform": platform or record.platform,
                    }

                record.last_heartbeat = now
                record.uptime_seconds = uptime_seconds
                record.scans_total += scans
                record.threats_total += threats
                record.last_known_status = "online"
                if version:
                    record.version = version
                if platform:
                    record.platform = platform
                if integration:
                    record.integration = integration
            else:
                # Create new - this is startup
                record = AgentRecord(
                    agent_id=agent_id,
                    mssp_id=mssp_id,
                    customer_id=customer_id,
                    version=version,
                    platform=platform,
                    integration=integration,
                    first_seen=now,
                    last_heartbeat=now,
                    uptime_seconds=uptime_seconds,
                    scans_total=scans,
                    threats_total=threats,
                    last_known_status="online",
                )
                self._agents[agent_id] = record

                # New agent = startup status change
                status_change = {
                    "agent_id": agent_id,
                    "mssp_id": mssp_id,
                    "customer_id": customer_id,
                    "previous_status": "unknown",
                    "new_status": "online",
                    "reason": "startup",
                    "agent_version": version,
                    "platform": platform,
                }

            self._save()

        return status_change

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        """Get agent record by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentRecord or None if not found
        """
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(
        self,
        mssp_id: str | None = None,
        customer_id: str | None = None,
    ) -> list[AgentRecord]:
        """List agents with optional filtering.

        Args:
            mssp_id: Filter by MSSP
            customer_id: Filter by customer

        Returns:
            List of matching AgentRecords
        """
        with self._lock:
            agents = list(self._agents.values())

        # Apply filters
        if mssp_id:
            agents = [a for a in agents if a.mssp_id == mssp_id]
        if customer_id:
            agents = [a for a in agents if a.customer_id == customer_id]

        return agents

    def get_agent_status(self, agent_id: str) -> str:
        """Calculate agent status based on last heartbeat.

        Args:
            agent_id: Agent identifier

        Returns:
            Status string: "online", "degraded", "offline", or "unknown"
        """
        record = self.get_agent(agent_id)

        if not record:
            return "unknown"

        if not record.last_heartbeat:
            return "unknown"

        try:
            last_hb = datetime.fromisoformat(record.last_heartbeat.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            seconds_since = (now - last_hb).total_seconds()

            if seconds_since <= self.config.online_threshold_seconds:
                return "online"
            elif seconds_since <= self.config.degraded_threshold_seconds:
                return "degraded"
            else:
                return "offline"
        except Exception:
            return "unknown"

    def get_agent_with_status(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent record with computed status.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict with agent data and status, or None
        """
        record = self.get_agent(agent_id)

        if not record:
            return None

        data = asdict(record)
        data["status"] = self.get_agent_status(agent_id)

        return data

    def list_agents_with_status(
        self,
        mssp_id: str | None = None,
        customer_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List agents with computed status.

        Args:
            mssp_id: Filter by MSSP
            customer_id: Filter by customer

        Returns:
            List of dicts with agent data and status
        """
        agents = self.list_agents(mssp_id=mssp_id, customer_id=customer_id)

        result = []
        for agent in agents:
            data = asdict(agent)
            data["status"] = self.get_agent_status(agent.agent_id)
            result.append(data)

        return result

    def count_active_agents(self, mssp_id: str, customer_id: str | None = None) -> int:
        """Count agents with online or degraded status for an MSSP.

        Args:
            mssp_id: MSSP identifier to filter by
            customer_id: Optional customer filter

        Returns:
            Count of active (online or degraded) agents
        """
        agents = self.list_agents(mssp_id=mssp_id, customer_id=customer_id)
        return sum(
            1 for agent in agents if self.get_agent_status(agent.agent_id) in ("online", "degraded")
        )

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from registry.

        Args:
            agent_id: Agent identifier

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                self._save()
                return True
            return False

    def check_for_status_changes(self) -> list[dict[str, Any]]:
        """Check all agents for status changes due to missed heartbeats.

        This should be called periodically to detect agents that have
        gone offline or degraded.

        Returns:
            List of status change dicts for agents whose status changed.
        """
        status_changes: list[dict[str, Any]] = []

        with self._lock:
            for agent_id, record in self._agents.items():
                current_status = self._compute_status(record.last_heartbeat)
                previous_status = record.last_known_status

                if current_status != previous_status:
                    # Determine reason based on transition
                    if current_status in ("offline", "degraded"):
                        reason = "no_heartbeat"
                    elif current_status == "online":
                        reason = "heartbeat_received"
                    else:
                        reason = "manual"

                    status_changes.append(
                        {
                            "agent_id": agent_id,
                            "mssp_id": record.mssp_id,
                            "customer_id": record.customer_id,
                            "previous_status": previous_status,
                            "new_status": current_status,
                            "reason": reason,
                            "agent_version": record.version,
                            "platform": record.platform,
                        }
                    )

                    # Update the stored status
                    record.last_known_status = current_status

            # Save if any changes
            if status_changes:
                self._save()

        return status_changes

    def _compute_status(self, last_heartbeat: str) -> str:
        """Compute agent status from last heartbeat time.

        Args:
            last_heartbeat: ISO8601 timestamp of last heartbeat

        Returns:
            Status string: "online", "degraded", "offline", or "unknown"
        """
        if not last_heartbeat:
            return "unknown"

        try:
            last_hb = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            seconds_since = (now - last_hb).total_seconds()

            if seconds_since <= self.config.online_threshold_seconds:
                return "online"
            elif seconds_since <= self.config.degraded_threshold_seconds:
                return "degraded"
            else:
                return "offline"
        except Exception:
            return "unknown"


# Global singleton
_registry: AgentRegistry | None = None
_registry_lock = threading.Lock()


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance.

    Returns:
        Singleton AgentRegistry instance
    """
    global _registry

    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = AgentRegistry()

    return _registry


__all__ = [
    "AgentRecord",
    "AgentRegistry",
    "AgentRegistryConfig",
    "get_agent_registry",
]
