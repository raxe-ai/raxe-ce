"""Multi-tenant policy management domain models.

This module provides tenant-level policy configuration for RAXE:
- TenantPolicy: Mode-based presets (monitor/balanced/strict)
- Tenant: Customer/organization entity
- App: Application within a tenant
- PolicyResolutionResult: Result of resolving which policy applies
- Global presets: POLICY_MONITOR, POLICY_BALANCED, POLICY_STRICT

Note: TenantPolicy is DIFFERENT from the existing Policy class in
domain/policies/models.py which provides granular conditions-based overrides.
"""

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    PolicyResolutionResult,
    Tenant,
    TenantPolicy,
)
from raxe.domain.tenants.presets import (
    GLOBAL_PRESETS,
    POLICY_BALANCED,
    POLICY_MONITOR,
    POLICY_STRICT,
)
from raxe.domain.tenants.repository import (
    AppRepository,
    PolicyRepository,
    TenantRepository,
)
from raxe.domain.tenants.resolver import resolve_policy

__all__ = [
    "GLOBAL_PRESETS",
    "POLICY_BALANCED",
    "POLICY_MONITOR",
    "POLICY_STRICT",
    "App",
    "AppRepository",
    "PolicyMode",
    "PolicyRepository",
    "PolicyResolutionResult",
    "Tenant",
    "TenantPolicy",
    "TenantRepository",
    "resolve_policy",
]
