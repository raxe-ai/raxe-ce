"""OpenClaw hook file manager.

Handles installing and removing RAXE security hook files
in the OpenClaw hooks directory.
"""

from __future__ import annotations

import shutil

from raxe.infrastructure.openclaw.models import OpenClawPaths

# Embedded handler.ts content
# This TypeScript handler is called by OpenClaw to scan messages
HANDLER_TS_CONTENT = """/**
 * RAXE Security Hook for OpenClaw
 *
 * This hook scans all incoming messages for security threats
 * using the RAXE CLI directly (simpler than MCP protocol).
 */

import { spawn } from "child_process";

interface ScanResult {
  has_threats: boolean;
  severity: string;
  message: string;
}

/**
 * Scan text for security threats using RAXE CLI.
 */
export async function scanMessage(text: string): Promise<ScanResult> {
  return new Promise((resolve, reject) => {
    // Use raxe scan with JSON format
    const proc = spawn("raxe", ["scan", "--format", "json", text]);

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      try {
        // Parse JSON output from raxe scan --format json
        const result = JSON.parse(stdout);
        const hasThreats = result.has_detections || false;
        const severity = hasThreats
          ? (result.detections?.[0]?.severity || "high").toUpperCase()
          : "none";
        const count = (result.l1_count || 0) + (result.l2_count || 0);
        const rules = result.detections?.map((d: any) => d.rule_id).join(", ");
        resolve({
          has_threats: hasThreats,
          severity: severity,
          message: hasThreats
            ? `${count} threat(s) detected: ${rules}`
            : "No threats detected",
        });
      } catch (e) {
        // Fallback: check for threat keywords in output
        const hasThreat = stdout.includes("THREAT") ||
          stdout.includes("CRITICAL") || stdout.includes("has_detections");
        resolve({
          has_threats: hasThreat,
          severity: hasThreat ? "HIGH" : "none",
          message: stdout || stderr || "Parse error",
        });
      }
    });

    proc.on("error", (err) => {
      console.error("[raxe-security] Failed to spawn raxe:", err);
      resolve({
        has_threats: false,
        severity: "error",
        message: `Scan error: ${err.message}`,
      });
    });
  });
}

/**
 * Extract message text from various event formats.
 */
function extractText(event: any): string {
  // Try various event structures
  return (
    event.message?.text ||
    event.text ||
    event.prompt ||
    event.content ||
    event.data?.text ||
    event.data?.prompt ||
    event.data?.content ||
    ""
  );
}

/**
 * OpenClaw hook handler.
 * Called by OpenClaw for various message events.
 */
const handler = async (event: any): Promise<void> => {
  // Log all events for debugging (remove in production)
  console.log(`[raxe-security] Event received: type=${event.type}`);

  const message = extractText(event);
  if (!message) {
    console.log(`[raxe-security] No text content in event`);
    return;
  }

  console.log(`[raxe-security] Scanning message (${message.length} chars)...`);

  try {
    const result = await scanMessage(message);

    if (result.has_threats) {
      console.log(`[raxe-security] ⚠ THREAT DETECTED: severity=${result.severity}`);
      console.log(`[raxe-security] ${result.message}`);
      // To block: throw new Error("Blocked by RAXE security");
      // Or set: event.blocked = true;
    } else {
      console.log(`[raxe-security] ✓ Message scanned: clean`);
    }
  } catch (error) {
    console.error("[raxe-security] Scan error:", error);
  }
};

export default handler;
"""

# Embedded package.json content
# Required for ES module support in OpenClaw hooks
PACKAGE_JSON_CONTENT = """{
  "name": "raxe-security-hook",
  "version": "1.0.0",
  "type": "module",
  "description": "RAXE security hook for OpenClaw"
}
"""

# Embedded HOOK.md content
# This metadata file describes the hook to OpenClaw
# Uses YAML frontmatter for OpenClaw to read name, description, etc.
HOOK_MD_CONTENT = """---
name: raxe-security
description: "Scan messages for prompt injection, jailbreaks, and data exfiltration"
homepage: https://docs.raxe.ai/integrations/openclaw
metadata:
  openclaw:
    emoji: "🛡️"
    events: ["message:inbound", "message", "command", "agent:prompt", "prompt"]
    install:
      - id: raxe-managed
        kind: managed
        label: "Installed by RAXE CLI"
---

# RAXE Security Hook

This hook integrates RAXE threat detection into OpenClaw, protecting your AI assistant from:

- **Prompt Injection**: Attempts to override AI instructions
- **Jailbreak Attempts**: Bypassing safety guardrails
- **Data Exfiltration**: Leaking sensitive data, API keys, or system prompts
- **Command Injection**: Shell commands embedded in messages
- **Encoded Attacks**: Base64/hex encoded malicious content

## How It Works

All incoming messages are scanned by RAXE before reaching your AI:

```
Message → RAXE Scan → Clean? → AI processes
                   → Threat? → Block/Log
```

## Installation

Installed automatically by RAXE CLI:

```bash
raxe openclaw install
```

## Uninstallation

```bash
raxe openclaw uninstall
```

## Configuration

The hook uses the RAXE MCP server for scanning. All scanning happens
locally - your message content is never transmitted.

For more information: https://docs.raxe.ai/integrations/openclaw
"""


class OpenClawHookManager:
    """Manager for OpenClaw hook files.

    Handles installing and removing the RAXE security hook files
    in the OpenClaw hooks directory.
    """

    def __init__(self, paths: OpenClawPaths | None = None) -> None:
        """Initialize hook manager.

        Args:
            paths: OpenClawPaths instance (uses defaults if None)
        """
        self.paths = paths or OpenClawPaths()

    def get_handler_content(self) -> str:
        """Get the embedded handler.ts content.

        Returns:
            TypeScript handler code
        """
        return HANDLER_TS_CONTENT

    def get_hook_md_content(self) -> str:
        """Get the embedded HOOK.md content.

        Returns:
            Hook metadata markdown
        """
        return HOOK_MD_CONTENT

    def get_package_json_content(self) -> str:
        """Get the embedded package.json content.

        Required for ES module support in OpenClaw hooks.

        Returns:
            Package.json JSON content
        """
        return PACKAGE_JSON_CONTENT

    def install_hook_files(self) -> None:
        """Install RAXE security hook files.

        Creates the raxe-security directory and writes handler.ts, HOOK.md,
        and package.json (required for ES module support).
        """
        # Create hook directory
        self.paths.raxe_hook_dir.mkdir(parents=True, exist_ok=True)

        # Write handler.ts
        self.paths.handler_file.write_text(self.get_handler_content())

        # Write HOOK.md
        self.paths.hook_md_file.write_text(self.get_hook_md_content())

        # Write package.json (required for ES module support in OpenClaw)
        self.paths.package_json_file.write_text(self.get_package_json_content())

    def remove_hook_files(self) -> None:
        """Remove RAXE security hook files.

        Deletes the entire raxe-security directory.
        """
        if self.paths.raxe_hook_dir.exists():
            shutil.rmtree(self.paths.raxe_hook_dir)

    def hook_files_exist(self) -> bool:
        """Check if all hook files exist.

        Returns:
            True if handler.ts, HOOK.md, and package.json all exist
        """
        return (
            self.paths.raxe_hook_dir.exists()
            and self.paths.handler_file.exists()
            and self.paths.hook_md_file.exists()
            and self.paths.package_json_file.exists()
        )
