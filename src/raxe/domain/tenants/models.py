"""Multi-tenant policy management domain models.

This module defines the core domain models for tenant-level policy configuration:
- PolicyMode: Enum for preset modes (monitor/balanced/strict/custom)
- TenantPolicy: Mode-based policy configuration for tenants
- Tenant: Customer/organization entity
- App: Application within a tenant
- PolicyResolutionResult: Result of resolving which policy applies

Note: TenantPolicy is DIFFERENT from the existing Policy class in
domain/policies/models.py which provides granular conditions-based overrides.
TenantPolicy provides mode-based presets for tenant defaults.
"""

from dataclasses import dataclass
from enum import Enum


class PolicyMode(Enum):
    """Policy mode presets.

    - MONITOR: Log-only mode, no blocking (observe threats, build baseline)
    - BALANCED: Block HIGH/CRITICAL threats with high confidence (default)
    - STRICT: Block all threats from MEDIUM and above
    - CUSTOM: Full customization of all settings
    """

    MONITOR = "monitor"
    BALANCED = "balanced"
    STRICT = "strict"
    CUSTOM = "custom"


# Valid values for validation
_VALID_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"})
_VALID_TELEMETRY_LEVELS = frozenset({"minimal", "standard", "verbose"})
_VALID_TIERS = frozenset({"free", "pro", "enterprise"})
_VALID_RESOLUTION_SOURCES = frozenset({"request", "app", "tenant", "partner", "system_default"})


@dataclass(frozen=True)
class TenantPolicy:
    """Tenant-level policy configuration.

    This is a mode-based preset configuration, different from the conditions-based
    Policy class in domain/policies/models.py.

    Attributes:
        policy_id: Unique identifier (e.g., "pol_{uuid}" or preset name "balanced")
        name: Human-readable name
        tenant_id: Owner tenant ID, or None for global presets
        mode: Policy mode preset (monitor/balanced/strict/custom)
        blocking_enabled: Master switch for blocking behavior
        block_severity_threshold: Minimum severity to trigger blocking
        block_confidence_threshold: Minimum confidence (0-1) to trigger blocking
        l2_enabled: Whether L2 ML detection is enabled
        l2_threat_threshold: L2 threat score threshold (0-1)
        telemetry_detail: Level of telemetry detail (minimal/standard/verbose)
        version: Policy version for tracking changes (default: 1)
        created_at: ISO timestamp of creation (optional)
        updated_at: ISO timestamp of last update (optional)
    """

    # Identity
    policy_id: str
    name: str
    tenant_id: str | None  # None = global preset

    # Core behavior
    mode: PolicyMode
    blocking_enabled: bool

    # Severity thresholds
    block_severity_threshold: str = "HIGH"
    block_confidence_threshold: float = 0.85

    # L2 configuration
    l2_enabled: bool = True
    l2_threat_threshold: float = 0.35

    # Telemetry detail level
    telemetry_detail: str = "standard"

    # Version tracking
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        """Validate field values after initialization."""
        if not self.policy_id:
            raise ValueError("policy_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not 0 <= self.block_confidence_threshold <= 1:
            raise ValueError("block_confidence_threshold must be 0-1")
        if not 0 <= self.l2_threat_threshold <= 1:
            raise ValueError("l2_threat_threshold must be 0-1")
        if self.block_severity_threshold not in _VALID_SEVERITIES:
            raise ValueError(f"block_severity_threshold must be one of {_VALID_SEVERITIES}")
        if self.telemetry_detail not in _VALID_TELEMETRY_LEVELS:
            raise ValueError(f"telemetry_detail must be one of {_VALID_TELEMETRY_LEVELS}")
        if self.version < 1:
            raise ValueError("version must be >= 1")


@dataclass(frozen=True)
class Tenant:
    """Customer/organization entity.

    Represents a tenant (customer) in the multi-tenant system. Each tenant
    has a default policy and can contain multiple apps.

    Attributes:
        tenant_id: Unique identifier (e.g., "acme" or "tenant_acme_a1b2c3")
        name: Human-readable name
        default_policy_id: Reference to default policy (e.g., "balanced")
        partner_id: Parent partner ID for B2B2C model (optional)
        tier: Subscription tier (free/pro/enterprise)
        created_at: ISO timestamp of creation (optional)
    """

    tenant_id: str
    name: str
    default_policy_id: str
    partner_id: str | None = None
    tier: str = "free"
    created_at: str | None = None

    def __post_init__(self) -> None:
        """Validate field values after initialization."""
        if not self.tenant_id:
            raise ValueError("tenant_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.default_policy_id:
            raise ValueError("default_policy_id cannot be empty")
        if self.tier not in _VALID_TIERS:
            raise ValueError(f"tier must be one of {_VALID_TIERS}")


@dataclass(frozen=True)
class App:
    """Application within a tenant.

    Represents an application belonging to a tenant. Apps can override
    the tenant's default policy.

    Attributes:
        app_id: Unique identifier within tenant (e.g., "chatbot")
        tenant_id: Owner tenant ID
        name: Human-readable name
        default_policy_id: Policy override, or None to inherit from tenant
        created_at: ISO timestamp of creation (optional)
    """

    app_id: str
    tenant_id: str
    name: str
    default_policy_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        """Validate field values after initialization."""
        if not self.app_id:
            raise ValueError("app_id cannot be empty")
        if not self.tenant_id:
            raise ValueError("tenant_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")


@dataclass(frozen=True)
class PolicyResolutionResult:
    """Result of resolving which policy applies.

    Contains the resolved policy along with metadata about how it was resolved.
    This is critical for audit/billing visibility.

    Attributes:
        policy: The resolved TenantPolicy to apply
        resolution_source: Where the policy came from (request/app/tenant/partner/system_default)
        resolution_path: Full chain attempted during resolution
    """

    policy: TenantPolicy
    resolution_source: str
    resolution_path: list[str]

    def __post_init__(self) -> None:
        """Validate field values after initialization."""
        if self.resolution_source not in _VALID_RESOLUTION_SOURCES:
            raise ValueError(f"resolution_source must be one of {_VALID_RESOLUTION_SOURCES}")
