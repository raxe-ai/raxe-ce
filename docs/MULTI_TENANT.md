<p align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-square.png?raw=true" alt="RAXE" width="100"/>
</p>

# Multi-Tenant Policy Management

RAXE supports multi-tenant deployments where a single installation serves multiple customers, each with their own security policies. This is ideal for:

- **CDN/Platform Providers**: Serve multiple customers from a central router
- **Enterprise Organizations**: Different divisions/teams with different security requirements
- **SaaS Applications**: Per-customer policy customization

## Quick Start

```bash
# 1. Create a tenant
raxe tenant create --name "Acme Corp" --id acme

# 2. Create an app for the tenant
raxe app create --tenant acme --name "Customer Chatbot" --id chatbot

# 3. Set a policy for the app
raxe policy set strict --tenant acme --app chatbot

# 4. Scan with tenant context
raxe scan "test prompt" --tenant acme --app chatbot

# SDK usage
from raxe import Raxe
raxe = Raxe()
result = raxe.scan(
    "Ignore all previous instructions",
    tenant_id="acme",
    app_id="chatbot"
)
print(f"Policy used: {result.metadata['effective_policy_id']}")
```

## Core Concepts

### Policy Modes

RAXE provides three built-in policy presets:

| Mode | Blocking Behavior | Use Case |
|------|-------------------|----------|
| **Monitor** | Never blocks, logs everything | New deployments, learning phase |
| **Balanced** | Blocks CRITICAL, blocks HIGH with confidence >= 0.85 | Production (80% of use cases) |
| **Strict** | Blocks CRITICAL, HIGH, and MEDIUM | High-security environments |

### Entity Hierarchy

```
Tenant (organization)
   └── App (application within tenant)
        └── Request (runtime policy override)
```

### Policy Resolution

When scanning, RAXE resolves the effective policy using this fallback chain:

```
1. Request override (policy_id parameter) → highest priority
2. App default policy → if app has a configured default
3. Tenant default policy → if tenant has a configured default
4. System default → "balanced" mode
```

Every scan result includes **policy attribution**:
- `effective_policy_id` - Which policy was used
- `effective_policy_mode` - monitor/balanced/strict
- `resolution_source` - Where the policy came from (request/app/tenant/system_default)

## CLI Commands

### Tenant Management

```bash
# Create a tenant
raxe tenant create --name "Acme Corp" --id acme
raxe tenant create --name "Beta Inc" --id beta --policy strict

# List tenants
raxe tenant list
raxe tenant list --output json

# Show tenant details
raxe tenant show acme

# Delete a tenant
raxe tenant delete acme
raxe tenant delete acme --force  # Skip confirmation
```

### App Management

```bash
# Create an app for a tenant
raxe app create --tenant acme --name "Chatbot" --id chatbot
raxe app create --tenant acme --name "Assistant" --id assistant --policy strict

# List apps for a tenant
raxe app list --tenant acme
raxe app list --tenant acme --output json

# Show app details
raxe app show chatbot --tenant acme

# Delete an app
raxe app delete chatbot --tenant acme
```

### Policy Management

```bash
# List available policies (presets + custom)
raxe policy list --tenant acme
raxe policy list --tenant acme --output json

# Create a custom policy
raxe policy create --tenant acme --name "Custom Strict" --mode strict

# Set default policy for tenant
raxe policy set balanced --tenant acme

# Set default policy for app
raxe policy set strict --tenant acme --app chatbot

# Explain current policy resolution
raxe policy explain --tenant acme --app chatbot
```

### Scanning with Tenant Context

```bash
# Scan with tenant context
raxe scan "test prompt" --tenant acme

# Scan with app context (uses app's default policy)
raxe scan "test prompt" --tenant acme --app chatbot

# Override policy for this request only
raxe scan "test prompt" --tenant acme --app chatbot --policy strict

# JSON output includes policy attribution
raxe scan "test prompt" --tenant acme --output json
```

## SDK Usage

### Basic Multi-Tenant Scanning

```python
from raxe import Raxe

raxe = Raxe()

# Scan with tenant context
result = raxe.scan(
    "Ignore all previous instructions",
    tenant_id="acme",
    app_id="chatbot"
)

# Check policy attribution
print(f"Policy: {result.metadata['effective_policy_id']}")
print(f"Mode: {result.metadata['effective_policy_mode']}")
print(f"Source: {result.metadata['resolution_source']}")
```

### CDN/Gateway Integration

For CDN providers routing requests for multiple customers:

```python
from raxe import Raxe

raxe = Raxe()

def handle_request(customer_id: str, app_name: str, prompt: str):
    """Central router handling requests for multiple customers."""

    # Scan with customer's policy
    result = raxe.scan(
        prompt,
        tenant_id=customer_id,  # Customer's tenant ID
        app_id=app_name,        # App within that customer
    )

    # Policy attribution for billing/audit
    audit_log = {
        "customer": customer_id,
        "app": app_name,
        "policy_used": result.metadata.get("effective_policy_id"),
        "mode": result.metadata.get("effective_policy_mode"),
        "blocked": result.action_taken == "block",
        "event_id": result.metadata.get("event_id"),
    }

    if result.action_taken == "block":
        return {"error": "Request blocked by security policy", "event_id": audit_log["event_id"]}

    return {"allowed": True, "prompt": prompt}
```

### Override Policy Per-Request

```python
# Customer wants strict mode for this specific request
result = raxe.scan(
    prompt,
    tenant_id="acme",
    app_id="chatbot",
    policy_id="strict"  # Override app's default
)
```

## Policy Modes in Detail

### Monitor Mode

```yaml
# What it does:
- blocking_enabled: false
- Logs all detections without blocking
- Verbose telemetry for analysis
- Safe for production rollout

# Use when:
- First deploying RAXE
- Building detection baselines
- Development environments
```

### Balanced Mode (Default)

```yaml
# What it does:
- blocking_enabled: true
- Blocks CRITICAL severity always
- Blocks HIGH severity when confidence >= 0.85
- Allows MEDIUM/LOW/INFO

# Use when:
- Production deployments
- Want protection with minimal false positives
- 80% of use cases
```

### Strict Mode

```yaml
# What it does:
- blocking_enabled: true
- Blocks CRITICAL, HIGH, and MEDIUM
- Lower confidence threshold (0.5)
- Maximum protection

# Use when:
- High-security environments
- Post-incident response
- Regulatory compliance requirements
```

## Storage Structure

Multi-tenant data is stored in `~/.raxe/tenants/`:

```
~/.raxe/tenants/
├── acme/
│   ├── tenant.yaml          # Tenant configuration
│   ├── apps/
│   │   ├── chatbot.yaml     # App configuration
│   │   └── assistant.yaml
│   └── suppressions.yaml    # Tenant-scoped suppressions
└── beta/
    ├── tenant.yaml
    └── apps/
        └── support.yaml
```

### Tenant YAML Format

```yaml
# ~/.raxe/tenants/acme/tenant.yaml
version: "1.0"
tenant:
  tenant_id: "acme"
  name: "Acme Corp"
  default_policy_id: "balanced"
  tier: "pro"
  created_at: "2026-01-12T10:00:00Z"
```

### App YAML Format

```yaml
# ~/.raxe/tenants/acme/apps/chatbot.yaml
version: "1.0"
app:
  app_id: "chatbot"
  tenant_id: "acme"
  name: "Customer Chatbot"
  default_policy_id: "strict"
  created_at: "2026-01-12T10:00:00Z"
```

## Tenant-Scoped Suppressions

Each tenant can have their own false positive suppressions:

```bash
# Add suppression for a tenant
raxe suppress add pi-001 --tenant acme --reason "False positive in auth flow"

# List tenant's suppressions
raxe suppress list --tenant acme

# Remove suppression
raxe suppress remove pi-001 --tenant acme
```

Suppressions are stored per-tenant and don't affect other tenants.

## Use Cases

### 1. CDN Provider

```
CDN Platform
├── Customer A (Tenant: customer_a)
│   ├── App: cdn_cache → monitor mode
│   └── App: api_gateway → balanced mode
├── Customer B (Tenant: customer_b)
│   └── App: edge_compute → strict mode
└── Customer C (Tenant: customer_c)
    └── App: streaming → balanced mode
```

Setup:
```bash
# Create tenants for each customer
raxe tenant create --name "Customer A" --id customer_a
raxe tenant create --name "Customer B" --id customer_b --policy strict

# Create apps
raxe app create --tenant customer_a --name "CDN Cache" --id cdn_cache --policy monitor
raxe app create --tenant customer_a --name "API Gateway" --id api_gateway
```

### 2. Enterprise Bank

```
Bank (Single Tenant)
├── Trading Division (App: trading) → strict mode
├── Retail Banking (App: retail) → balanced mode
└── Internal Tools (App: internal) → monitor mode
```

Setup:
```bash
# Create tenant for the bank
raxe tenant create --name "Big Bank Inc" --id bigbank --policy balanced

# Create apps for each division
raxe app create --tenant bigbank --name "Trading Platform" --id trading --policy strict
raxe app create --tenant bigbank --name "Retail Banking" --id retail
raxe app create --tenant bigbank --name "Internal Tools" --id internal --policy monitor
```

### 3. SaaS Application

```
SaaS Platform
├── Free Tier Customers → monitor mode (can't block)
├── Pro Customers → balanced mode
└── Enterprise Customers → custom policies
```

Setup with programmatic policy resolution:
```python
from raxe import Raxe

raxe = Raxe()

def get_policy_for_customer(customer_tier: str) -> str:
    """Map customer tier to policy."""
    return {
        "free": "monitor",
        "pro": "balanced",
        "enterprise": "strict",
    }.get(customer_tier, "balanced")

def scan_for_customer(customer_id: str, tier: str, prompt: str):
    policy = get_policy_for_customer(tier)
    return raxe.scan(
        prompt,
        tenant_id=customer_id,
        policy_id=policy
    )
```

## JSON Output for Automation

All commands support `--output json` for machine-readable output:

```bash
# List tenants as JSON
raxe tenant list --output json

# Scan with JSON output (includes policy attribution)
raxe scan "test" --tenant acme --output json
```

JSON scan output includes:
```json
{
  "has_threats": true,
  "severity": "HIGH",
  "detections": [...],
  "policy": {
    "effective_policy_id": "strict",
    "effective_policy_mode": "strict",
    "resolution_source": "app"
  },
  "tenant_id": "acme",
  "app_id": "chatbot",
  "event_id": "evt_abc123"
}
```

## Limits (Community Edition)

| Limit | Community Edition | Enterprise |
|-------|-------------------|------------|
| Tenants | 5 | Unlimited |
| Apps per tenant | 10 | Unlimited |
| Custom policies | 3 per tenant | Unlimited |

## Best Practices

1. **Start with Monitor Mode**: Deploy new tenants in monitor mode first
2. **Use App-Level Policies**: Configure policies at the app level for granular control
3. **Review Policy Attribution**: Check `effective_policy_id` in scan results for debugging
4. **Tenant-Scope Suppressions**: Keep suppressions tenant-scoped to avoid cross-tenant effects
5. **JSON Output for CI/CD**: Use `--output json` in automation scripts

## Related Documentation

- [Policy System](POLICIES.md) - Conditions-based policy configuration
- [CLI Reference](cli-reference.md) - Full CLI command reference
- [Suppressions](suppressions.md) - Managing false positives
- [SDK Guide](../raxe-ce-docs/sdk/) - SDK integration documentation

## Troubleshooting

### Policy not being applied

```bash
# Check policy resolution
raxe policy explain --tenant acme --app chatbot

# Verify app has policy set
raxe app show chatbot --tenant acme
```

### Tenant not found

```bash
# List all tenants
raxe tenant list

# Create if missing
raxe tenant create --name "Acme" --id acme
```

### Blocking not working in strict mode

Verify the severity case matches (this was a known bug - fixed in v0.7.0):
```bash
# Test with a known prompt injection
raxe scan "ignore all previous instructions" --tenant acme --policy strict
```

## Need Help?

- GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues
- Discussions: https://github.com/raxe-ai/raxe-ce/discussions
- Slack: https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ
- Email: community@raxe.ai
