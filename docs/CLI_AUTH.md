# CLI Authentication Guide

This guide covers authentication commands for linking your RAXE CLI with your RAXE account, enabling access to permanent API keys and preserving your scan history.

## Overview

RAXE CLI supports three authentication flows:

| Flow | Command | Use Case |
|------|---------|----------|
| Browser Auth | `raxe auth` | New users - creates account and links CLI |
| Link Code | `raxe link <CODE>` | Existing users with Console-created keys |
| Manual | `raxe config set api_key <KEY>` | Direct key configuration |

## Quick Start

```bash
# New user? Run auth to create account and get permanent key
raxe auth

# Have a key from Console? Use the 6-character link code
raxe link ABC123

# Already have an API key? Set it directly
raxe config set api_key raxe_live_xxxxx
```

---

## raxe auth

Authenticate with RAXE Console via browser to upgrade from a temporary key to a permanent key.

### Usage

```bash
raxe auth [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--no-link-history` | | Do not link existing CLI history to the new account |
| `--no-browser` | `-n` | Print URL instead of opening browser |
| `--timeout` | `-t` | Polling timeout in seconds (default: 300) |
| `--json` | `-j` | Output result as JSON |

### How It Works

1. CLI creates a session with the backend, including your temp key ID
2. Browser opens to RAXE Console login page
3. You authenticate (email link or existing session)
4. Click "Connect CLI" in Console
5. CLI receives new permanent API key
6. Your CLI scan history is preserved

### Key ID Preservation (Default Behavior)

When you run `raxe auth`, your existing scan history is **automatically linked** to your new account:

- Your temp key's `keyId` (used for BigQuery lookups) is transferred to your new permanent key
- All historical scans remain associated with your account
- No data migration needed - it's seamless

**Opt out:** If you prefer to start fresh without linking existing history, use:
```bash
raxe auth --no-link-history
```

### Examples

```bash
# Standard auth flow
raxe auth
# Output:
# Opening browser for authentication...
# Waiting for authorization (timeout: 5 minutes)...
#
# [Browser opens https://console.raxe.ai/cli-auth?session=xxx]
#
# Authorization successful!
# New API key: raxe_live_abc...def (shown once, save it!)
# Key ID: key_23cc2f9f21f9
# Historical events preserved: 42 scans
#
# Your CLI is now authenticated.

# If browser doesn't open automatically
raxe auth --no-browser
# Output:
# Open this URL in your browser:
# https://console.raxe.ai/cli-auth?session=xxx
#
# Waiting for authorization...

# JSON output for scripting
raxe auth --json
# {"status": "success", "key_id": "key_23cc2f9f21f9", "events_preserved": 42}

# Start fresh without linking existing history
raxe auth --no-link-history
# Output:
# History linking disabled (--no-link-history)
# Opening browser for authentication...
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Authentication successful |
| `1` | Authentication failed or cancelled |
| `2` | Timeout waiting for browser auth |
| `3` | Network error |

---

## raxe link

Link your CLI to an existing API key using a 6-character code from RAXE Console.

### Usage

```bash
raxe link <CODE> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `CODE` | Yes | 6-character link code from Console (e.g., `ABC123`) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | `-j` | Output result as JSON |

### How It Works

1. In RAXE Console, go to API Keys
2. Click the "..." menu on any key, select "Link CLI"
3. A 6-character code is displayed (valid for 15 minutes)
4. Run `raxe link <CODE>` in your terminal
5. Your CLI is now using that key with history preserved

### Key ID Preservation

The `raxe link` command preserves your CLI scan history by updating the Console key's `keyId` to match your temp key's ID.

**Important:** This generates a new API key secret. If you were using the original key elsewhere, those integrations will need the new key.

### Examples

```bash
# Link CLI to Console key
raxe link ABC123
# Output:
# Linking CLI to API key...
#
# Success!
# New API key: raxe_live_xyz...789 (shown once, save it!)
# Key ID: key_23cc2f9f21f9
# Historical events preserved: 42 scans
#
# Your CLI is now linked to your Console key.

# JSON output
raxe link ABC123 --json
# {"status": "success", "key_id": "key_23cc2f9f21f9", "events_preserved": 42}

# Invalid or expired code
raxe link INVALID
# Error: Link code not found or expired.
# Generate a new code in Console: https://console.raxe.ai/keys
```

### Link Code Details

| Property | Value |
|----------|-------|
| Format | 6 uppercase alphanumeric characters |
| Validity | 15 minutes from generation |
| Single use | Yes - code is deleted after use |
| Case sensitive | No - converted to uppercase |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Link successful |
| `1` | Invalid or expired code |
| `2` | No temp key to preserve (run some scans first) |
| `3` | Network error |

---

## raxe auth status

Check your current authentication status and key validity.

### Usage

```bash
raxe auth status [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--remote` | Validate key with server (slower, more accurate) |
| `--json` | Output as JSON |

### Examples

```bash
# Local status check (fast)
raxe auth status
# Output:
# API Key Status
# ==============
# Key Type: live
# Key ID: key_23cc2f9f21f9
# Tier: community
# Created: 2025-01-20
#
# Features:
#   Telemetry Required: Yes
#   Can Disable Telemetry: No

# With temporary key
raxe auth status
# Output:
# API Key Status
# ==============
# Key Type: temporary
# Key ID: key_abc123...
# Expires: 2025-02-03 (10 days remaining)
#
# TIP: Run 'raxe auth' to get a permanent key

# Remote validation
raxe auth status --remote
# Output:
# API Key Status (validated with server)
# ======================================
# Key Type: live
# Key ID: key_23cc2f9f21f9
# Tier: pro
# Last Server Check: 2025-01-22T15:30:00Z
#
# Server-Confirmed Features:
#   Rate Limit: 500 req/min
#   Daily Limit: 1M events
#   Can Disable Telemetry: Yes
```

---

## Troubleshooting

### "Browser didn't open"

```bash
# Use --no-browser to get URL manually
raxe auth --no-browser
```

Then copy the URL and paste into your browser.

### "Session expired before completion"

The auth session expires after 5 minutes. If you take too long in the browser:

```bash
# Start a new session
raxe auth
```

### "Link code not found or expired"

Link codes expire after 15 minutes. Generate a new one in Console:

1. Go to https://console.raxe.ai/keys
2. Find your key
3. Click "..." menu > "Link CLI"
4. Copy the new code

### "No temp key found"

The `raxe link` command needs existing CLI history to preserve. Run some scans first:

```bash
raxe scan "test prompt"
raxe scan "another test"
raxe link ABC123  # Now this will work
```

### "Authentication failed"

Check your network connection and try again:

```bash
# Test connectivity
raxe doctor

# Retry auth
raxe auth
```

### Credentials file location

Credentials are stored at `~/.raxe/credentials.json`:

```json
{
  "api_key": "raxe_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "key_type": "live",
  "installation_id": "inst_xxxxxxxxxxxxxxxx",
  "created_at": "2025-01-22T10:00:00Z",
  "tier": "community"
}
```

To reset and start fresh:

```bash
rm ~/.raxe/credentials.json
raxe auth
```

---

## Security Considerations

### Key Storage

- API keys are stored in `~/.raxe/credentials.json`
- File permissions are set to `600` (owner read/write only)
- Keys are never logged or sent in error reports

### Key Types

| Type | Prefix | Duration | Telemetry |
|------|--------|----------|-----------|
| Temporary | `raxe_temp_` | 14 days | Required |
| Live | `raxe_live_` | Permanent | Tier-dependent |
| Test | `raxe_test_` | Permanent | Not sent |

### Rotating Keys

If you suspect key compromise:

1. Go to Console > API Keys
2. Revoke the compromised key
3. Create a new key
4. Update CLI: `raxe config set api_key <NEW_KEY>`

---

## Multiple Machines

If you use RAXE CLI on multiple machines:

**Option 1: Share credentials (simple)**
```bash
# On primary machine, after auth
scp ~/.raxe/credentials.json user@other-machine:~/.raxe/
```

**Option 2: Separate keys (recommended for teams)**
1. Run `raxe auth` on each machine
2. Each gets its own permanent key
3. All keys linked to same account in Console

---

## Environment Variables

Override credentials via environment:

```bash
# Use a specific API key
export RAXE_API_KEY=raxe_live_xxxxx
raxe scan "test"  # Uses env var key

# Useful for CI/CD where you don't want to store credentials
```

---

## Related Documentation

- [CLI Reference](cli-reference.md) - Complete CLI command reference
- [Configuration Guide](configuration.md) - Full configuration options
- [Getting Started](getting-started.md) - Installation and first steps
