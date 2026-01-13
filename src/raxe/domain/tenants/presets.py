"""Global policy presets for multi-tenant policy management.

This module defines immutable preset policies that serve as system defaults:
- POLICY_MONITOR: Log-only mode, no blocking (observe threats)
- POLICY_BALANCED: Block HIGH/CRITICAL with high confidence (default)
- POLICY_STRICT: Block all threats from MEDIUM and above

These presets have tenant_id=None indicating they are global/system-level.
Tenants can reference these presets or create custom policies based on them.
"""

from raxe.domain.tenants.models import PolicyMode, TenantPolicy

# Monitor Mode - "See everything, block nothing, learn fast"
# For: New adopters, development/staging, security researchers, compliance auditors
POLICY_MONITOR = TenantPolicy(
    policy_id="monitor",
    name="Monitor Mode",
    tenant_id=None,  # Global preset
    mode=PolicyMode.MONITOR,
    blocking_enabled=False,
    block_severity_threshold="INFO",  # Log everything
    block_confidence_threshold=0.3,  # Low bar to capture edge cases
    l2_enabled=True,  # Full ML detection for learning
    l2_threat_threshold=0.35,
    telemetry_detail="verbose",  # Maximum data for analysis
)

# Balanced Mode (DEFAULT) - "Block the dangerous, flag the suspicious, allow the rest"
# For: Production customer-facing apps, enterprise deployments, SaaS platforms
POLICY_BALANCED = TenantPolicy(
    policy_id="balanced",
    name="Balanced Mode",
    tenant_id=None,  # Global preset
    mode=PolicyMode.BALANCED,
    blocking_enabled=True,
    block_severity_threshold="HIGH",  # Block from HIGH and above
    block_confidence_threshold=0.85,  # Higher bar for blocking
    l2_enabled=True,
    l2_threat_threshold=0.35,
    telemetry_detail="standard",
)

# Strict Mode - "When in doubt, block it out"
# For: High-security environments, financial trading, AI with elevated privileges
POLICY_STRICT = TenantPolicy(
    policy_id="strict",
    name="Strict Mode",
    tenant_id=None,  # Global preset
    mode=PolicyMode.STRICT,
    blocking_enabled=True,
    block_severity_threshold="MEDIUM",  # Block from MEDIUM and above
    block_confidence_threshold=0.5,  # Lower bar for more aggressive blocking
    l2_enabled=True,
    l2_threat_threshold=0.35,
    telemetry_detail="verbose",  # Maximum visibility for security
)

# Dictionary of all global presets for easy lookup
GLOBAL_PRESETS: dict[str, TenantPolicy] = {
    "monitor": POLICY_MONITOR,
    "balanced": POLICY_BALANCED,
    "strict": POLICY_STRICT,
}
