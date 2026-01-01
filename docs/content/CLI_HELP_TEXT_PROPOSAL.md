# CLI Help Text Proposal

This document contains proposed help text updates for authentication commands.

---

## Proposed: `raxe auth --help`

```
Usage: raxe auth [OPTIONS] COMMAND [ARGS]...

  Authenticate your CLI with RAXE.

  WHICH METHOD TO USE:
    raxe auth         - Browser opens automatically (recommended)
    raxe auth login   - Get URL to open manually (headless/SSH)
    raxe link CODE    - Link to existing key from Console

  For CI/CD, set RAXE_API_KEY environment variable instead.

Options:
  --no-link-history  Start fresh without preserving scan history
  --help             Show this message and exit.

Commands:
  connect  Browser auth - opens browser automatically (default)
  login    Manual auth - prints URL for headless/SSH environments
  link     Link to existing Console key using 6-character code
  status   Show current authentication status

Examples:
  raxe auth                    # New user: creates account + links CLI
  raxe auth login              # SSH: get URL to open elsewhere
  raxe link ABC123             # Link to existing key from Console
  raxe auth status --remote    # Check key validity with server
```

**Character count: ~850 (fits standard terminal width)**

---

## Proposed: `raxe auth connect --help`

```
Usage: raxe auth connect [OPTIONS]

  Connect CLI to your RAXE account via browser (recommended).

  Opens your browser for one-click authentication. Your CLI will be
  automatically configured with a permanent API key.

  Your existing scan history is preserved by default.

  NO BROWSER? Use 'raxe auth login' instead to get a URL you can open
  on another device.

Options:
  --no-link-history  Do not link existing CLI history to the account
  --help             Show this message and exit.

Examples:
  raxe auth                    # Default - opens browser
  raxe auth --no-link-history  # Start fresh, don't preserve history
```

---

## Proposed: `raxe auth login --help`

```
Usage: raxe auth login [OPTIONS]

  Get authentication URL for manual setup (headless/SSH).

  Use this when you cannot open a browser on this machine.
  Prints a URL that you can open on your laptop or phone.

  After creating your key in the Console, configure it:
    raxe config set api_key YOUR_KEY

  Or set the environment variable:
    export RAXE_API_KEY=YOUR_KEY

  HAVE A BROWSER? Use 'raxe auth' instead for automatic setup.

Options:
  --help  Show this message and exit.

Examples:
  raxe auth login              # Prints URL to visit
  # Open URL on another device, create key
  raxe config set api_key raxe_live_xxxxx
```

---

## Proposed: `raxe link --help`

```
Usage: raxe link CODE [OPTIONS]

  Link CLI to an existing API key using a 6-character code.

  Get a link code from RAXE Console:
    1. Go to API Keys page
    2. Click ... on any key
    3. Select "Link CLI"
    4. Copy the 6-character code

  This preserves your CLI scan history and links it to that key.

  FIRST TIME USER? Use 'raxe auth' instead - it creates an account
  and key in one step.

Arguments:
  CODE  6-character link code from Console (e.g., ABC123)  [required]

Options:
  --help  Show this message and exit.

Examples:
  raxe link ABC123             # Link to key using code
  raxe auth link ABC123        # Same command, alternative syntax
```

---

## In-Product Error Messages

### When `raxe auth` fails to open browser

**Current:**
```
Could not open browser. Please visit:
https://console.raxe.ai/cli-auth?session=xxx
```

**Proposed:**
```
Could not open browser automatically.

OPTIONS:
  1. Copy this URL and open in any browser:
     https://console.raxe.ai/cli-auth?session=xxx

  2. Or use the headless flow:
     raxe auth login
     (Gives you a URL to open on another device)

Waiting for authentication...
```

### When `raxe link` has no history to preserve

**Current:**
```
No CLI history found.

The raxe link command is used to link existing CLI history
to an API key you've already created in the Console.

For first-time setup, use:
  raxe auth  - Connect your CLI to your RAXE account
```

**Proposed:**
```
No CLI history found.

The 'raxe link' command preserves existing scan history when
linking to a Console key. You don't have any history yet.

INSTEAD, USE:
  raxe auth           # Creates account + key automatically

  Or if you have a key already:
  raxe config set api_key YOUR_KEY
```

### When user runs wrong command for their situation

**Scenario: User on SSH tries `raxe auth`**

If browser fails to open, add this guidance:
```
Tip: On headless systems (SSH, Docker), use:
  raxe auth login

This gives you a URL to open on another device.
```

**Scenario: User already has key, tries `raxe auth`**

**Current:** Asks "Re-authenticate with a different account?"

**Proposed addition after "Already authenticated!":**
```
Already authenticated!
  API Key: raxe_live_abc...xyz

OTHER OPTIONS:
  raxe auth status      # View key details and usage
  raxe link CODE        # Switch to different Console key

Re-authenticate with a different account? [y/N]
```

---

## Implementation Notes

### Changes to `src/raxe/cli/auth.py`

1. **Update `@click.group` docstring** for `auth` command
2. **Update `auth_connect` docstring** with fallback guidance
3. **Update `auth_login` docstring** to clarify use case
4. **Update `auth_link` docstring** with first-time user note
5. **Enhance browser failure message** in `auth_connect`
6. **Enhance "already authenticated" message** to show options

### Key Principles Applied

1. **Show alternatives at decision points** - Don't just fail, guide to right path
2. **Use ALL CAPS for section headers** in help - Scannable
3. **Lead with use case** - "headless/SSH" not technical details
4. **Include examples** - Developers learn from examples
5. **Keep it short** - Target 20 lines max for primary help
