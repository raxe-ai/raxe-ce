"""Policy resolution engine for multi-tenant policy management.

This module provides the resolve_policy() function that implements the
hierarchical policy resolution algorithm:

    Request → App → Tenant → System Default

The resolver is a PURE FUNCTION with no I/O, making it easy to test
and reason about.
"""

from raxe.domain.tenants.models import (
    App,
    PolicyResolutionResult,
    Tenant,
    TenantPolicy,
)


def resolve_policy(
    request_policy_id: str | None,
    app: App | None,
    tenant: Tenant | None,
    policy_registry: dict[str, TenantPolicy],
    system_default_id: str = "balanced",
) -> PolicyResolutionResult:
    """Resolve the effective policy for a scan request.

    Implements hierarchical resolution with fallback chain:
    1. Request-level policy_id override (highest priority)
    2. App default policy
    3. Tenant default policy
    4. System default (balanced mode)

    This is a PURE FUNCTION with no I/O. All policy lookups are done
    against the provided policy_registry.

    Args:
        request_policy_id: Explicit policy ID from scan request (optional)
        app: App context for the request (optional)
        tenant: Tenant context for the request (optional)
        policy_registry: Dictionary of policy_id -> TenantPolicy
        system_default_id: Policy ID to use as system default (default: "balanced")

    Returns:
        PolicyResolutionResult containing:
        - policy: The resolved TenantPolicy
        - resolution_source: Where the policy came from
        - resolution_path: Full chain showing resolution process

    Examples:
        >>> from raxe.domain.tenants.presets import GLOBAL_PRESETS
        >>> result = resolve_policy(
        ...     request_policy_id="strict",
        ...     app=None,
        ...     tenant=None,
        ...     policy_registry=GLOBAL_PRESETS,
        ... )
        >>> result.policy.policy_id
        'strict'
        >>> result.resolution_source
        'request'
    """
    resolution_path: list[str] = []

    # 1. Request-level override (highest priority)
    if request_policy_id is not None:
        resolution_path.append(f"request:{request_policy_id}")
        if request_policy_id in policy_registry:
            return PolicyResolutionResult(
                policy=policy_registry[request_policy_id],
                resolution_source="request",
                resolution_path=resolution_path,
            )
        # Invalid request policy_id - continue to fallback
    else:
        resolution_path.append("request:None")

    # 2. App default policy
    if app is not None:
        resolution_path.append(f"app:{app.app_id}")
        if app.default_policy_id and app.default_policy_id in policy_registry:
            return PolicyResolutionResult(
                policy=policy_registry[app.default_policy_id],
                resolution_source="app",
                resolution_path=resolution_path,
            )
        # App has no default or invalid policy_id - continue to fallback

    # 3. Tenant default policy
    if tenant is not None:
        resolution_path.append(f"tenant:{tenant.tenant_id}")
        if tenant.default_policy_id in policy_registry:
            return PolicyResolutionResult(
                policy=policy_registry[tenant.default_policy_id],
                resolution_source="tenant",
                resolution_path=resolution_path,
            )
        # Tenant's policy_id not in registry - continue to fallback

    # 4. System default (lowest priority)
    resolution_path.append(f"system:{system_default_id}")
    return PolicyResolutionResult(
        policy=policy_registry[system_default_id],
        resolution_source="system_default",
        resolution_path=resolution_path,
    )
