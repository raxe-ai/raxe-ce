# Authentication Decision Guide

Quick reference for choosing the right RAXE authentication method.

---

## Decision Tree

```
START: How do you want to authenticate?
|
+-- Can you open a browser on this machine?
|   |
|   +-- YES --> Do you have an existing RAXE account?
|   |           |
|   |           +-- NO --> Use: raxe auth
|   |           |          (Creates account + links CLI in one step)
|   |           |
|   |           +-- YES --> Do you want to link to an existing API key?
|   |                       |
|   |                       +-- YES --> Use: raxe link <CODE>
|   |                       |          (Get code from Console > API Keys > Link CLI)
|   |                       |
|   |                       +-- NO --> Use: raxe auth
|   |                                  (Creates new key linked to your account)
|   |
|   +-- NO (headless/SSH/container)
|       |
|       +-- Is this for CI/CD or automation?
|           |
|           +-- YES --> Use: Environment variable
|           |          export RAXE_API_KEY=raxe_live_xxx
|           |
|           +-- NO --> Use: raxe auth login
|                      (Gives you a URL to open on another device)
|                      Then: raxe config set api_key YOUR_KEY
```

---

## Method Comparison

| Method | Command | Browser Required | Creates Account | Preserves History | Best For |
|--------|---------|------------------|-----------------|-------------------|----------|
| Browser Auth | `raxe auth` | Yes (auto-opens) | Yes, if needed | Yes | New users, laptops |
| Manual URL | `raxe auth login` | No (copy URL) | No | No | SSH, headless servers |
| Link Code | `raxe link CODE` | No | No | Yes | Linking to existing key |
| Direct Config | `raxe config set api_key` | No | No | No | CI/CD, existing keys |
| Environment | `RAXE_API_KEY=xxx` | No | No | No | CI/CD, containers |

---

## Quick Reference

### New User (First Time)
```bash
raxe auth
```
Opens browser, creates account if needed, automatically configures CLI.

### SSH / Headless Server
```bash
# Step 1: Get the auth URL
raxe auth login

# Step 2: Open URL on your laptop/phone, create key
# Step 3: Configure the key
raxe config set api_key raxe_live_xxxxx
```

### CI/CD Pipeline
```yaml
# GitHub Actions
env:
  RAXE_API_KEY: ${{ secrets.RAXE_API_KEY }}

# Docker
docker run -e RAXE_API_KEY=raxe_live_xxx myapp
```

### Link Existing Key (Preserve History)
```bash
# In Console: API Keys > ... > Link CLI
# Get the 6-character code, then:
raxe link ABC123
```

---

## When to Use Each Method

### `raxe auth` - Browser Flow (Recommended)
**Use when:**
- You can open a browser on this machine
- You want the simplest setup
- You're a new user creating an account
- You want CLI scan history linked to your account

**What happens:**
1. Opens browser to RAXE Console
2. You sign in or create account
3. CLI automatically receives API key
4. Previous scans are linked to your account

### `raxe auth login` - Manual URL Flow
**Use when:**
- No GUI/browser available (SSH, Docker, remote server)
- You want to open the URL on a different device
- Firewall blocks browser auto-open

**What happens:**
1. Prints a URL to visit
2. You open URL on any device with a browser
3. Create key in Console
4. Manually configure: `raxe config set api_key YOUR_KEY`

### `raxe link CODE` - Link Code Flow
**Use when:**
- You already have an API key in RAXE Console
- You want to connect CLI to that specific key
- You want to preserve CLI scan history

**What happens:**
1. You generate a 6-char code in Console
2. Run `raxe link CODE` in CLI
3. CLI is linked to that key with history preserved

### Environment Variable / Direct Config
**Use when:**
- CI/CD pipelines
- Docker containers
- Kubernetes deployments
- Any automated environment

**What happens:**
- Key is read from `RAXE_API_KEY` env var
- Or from `~/.raxe/config.yaml` via `raxe config set`

---

## Error Recovery

### "Could not open browser"
You're on a headless system. Use the manual flow:
```bash
raxe auth login
# Copy the URL, open on another device
raxe config set api_key YOUR_KEY
```

### "Session expired"
Auth sessions last 5 minutes. Just run again:
```bash
raxe auth
```

### "No CLI history found" (raxe link)
The `raxe link` command requires prior CLI usage. Either:
```bash
# Option A: Run some scans first
raxe scan "test"
raxe link ABC123

# Option B: Use raxe auth instead (works without history)
raxe auth
```

### "Link code not found or expired"
Link codes expire after 15 minutes. Generate a new one:
1. Go to Console > API Keys
2. Click ... > Link CLI
3. Use the new code immediately

---

## CI/CD Examples

### GitHub Actions
```yaml
name: Security Scan
on: [push]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install RAXE
        run: pip install raxe
      - name: Run scan
        env:
          RAXE_API_KEY: ${{ secrets.RAXE_API_KEY }}
        run: raxe scan "$(cat prompt.txt)"
```

### Docker
```dockerfile
FROM python:3.11-slim
RUN pip install raxe
# Key passed at runtime, not baked in
CMD ["raxe", "scan", "test"]
```

```bash
docker run -e RAXE_API_KEY=raxe_live_xxx myapp
```

### Docker Compose
```yaml
services:
  app:
    image: myapp
    environment:
      - RAXE_API_KEY=${RAXE_API_KEY}
```

### Kubernetes
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: raxe-secrets
stringData:
  api-key: raxe_live_xxxxx
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          env:
            - name: RAXE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: raxe-secrets
                  key: api-key
```

---

## Priority Order

RAXE checks for API keys in this order:

1. `RAXE_API_KEY` environment variable (highest priority)
2. `~/.raxe/config.yaml` (explicit configuration)
3. `~/.raxe/credentials.json` (from `raxe auth`)

This means environment variables always win, making CI/CD overrides simple.
