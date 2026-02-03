#!/usr/bin/env python3
# ruff: noqa: T201, S104, S603, A002, N802
"""RAXE Webhook Test Server.

A development server to receive and display MSSP webhook payloads from RAXE.
Supports HTTPS with auto-generated self-signed certificates.

Features:
- HTTPS with auto-generated self-signed certificates
- HMAC-SHA256 signature verification
- Pretty-printed webhook payloads with threat highlighting
- Color-coded output for easy reading

Usage:
    python scripts/webhook_test_server.py [--port PORT] [--secret SECRET]

Examples:
    # Start HTTPS server (generates self-signed cert)
    python scripts/webhook_test_server.py --port 9001 --secret my_secret

    # Start with full JSON output (no truncation)
    python scripts/webhook_test_server.py --port 9001 --secret my_secret --full-json

    # Then configure RAXE MSSP:
    raxe mssp create --id test_mssp --name "Test MSSP" \\
        --webhook-url https://127.0.0.1:9001/raxe/alerts \\
        --webhook-secret my_secret

    # Test the webhook:
    RAXE_SKIP_SSL_VERIFY=true raxe mssp test-webhook test_mssp

Note:
    When testing with self-signed certificates, set RAXE_SKIP_SSL_VERIFY=true
    to bypass SSL certificate verification in the RAXE CLI.
"""

import argparse
import hashlib
import hmac
import json
import os
import ssl
import subprocess
import sys
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def generate_self_signed_cert(cert_dir: str) -> tuple[str, str]:
    """Generate a self-signed certificate for HTTPS.

    Args:
        cert_dir: Directory to store certificate files.

    Returns:
        Tuple of (cert_file_path, key_file_path).
    """
    cert_file = os.path.join(cert_dir, "server.crt")
    key_file = os.path.join(cert_dir, "server.key")

    if os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"{DIM}Using existing certificate: {cert_file}{RESET}")
        return cert_file, key_file

    print(f"{YELLOW}Generating self-signed certificate...{RESET}")

    # Generate using openssl
    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        key_file,
        "-out",
        cert_file,
        "-days",
        "365",
        "-nodes",  # No password
        "-subj",
        "/CN=localhost/O=RAXE Test/C=US",
        "-addext",
        "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"{GREEN}Certificate generated: {cert_file}{RESET}")
        return cert_file, key_file
    except subprocess.CalledProcessError as e:
        print(f"{RED}Failed to generate certificate: {e.stderr.decode()}{RESET}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"{RED}openssl not found. Please install OpenSSL.{RESET}")
        sys.exit(1)


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming webhook requests."""

    webhook_secret = "test-secret"
    request_count = 0
    full_json = False  # Show full JSON without truncation

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass

    def do_POST(self) -> None:
        """Handle POST requests (webhooks)."""
        WebhookHandler.request_count += 1
        request_num = WebhookHandler.request_count

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Get headers
        signature = self.headers.get("X-Raxe-Signature", "")
        timestamp = self.headers.get("X-Raxe-Timestamp", "")
        content_type = self.headers.get("Content-Type", "")

        # Print separator
        print(f"\n{BOLD}{BLUE}{'═' * 80}{RESET}")
        print(
            f"{BOLD}Webhook #{request_num}{RESET} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"{BLUE}{'─' * 80}{RESET}")

        # Print request info
        print(f"{DIM}Path:{RESET} {self.path}")
        print(f"{DIM}Content-Type:{RESET} {content_type}")
        print(f"{DIM}Content-Length:{RESET} {content_length} bytes")

        # Verify signature
        if signature and timestamp:
            expected_signature = self._compute_signature(timestamp, body)
            if hmac.compare_digest(expected_signature, signature):
                print(f"{DIM}Signature:{RESET} {GREEN}✓ Valid{RESET}")
            else:
                print(f"{DIM}Signature:{RESET} {RED}✗ Invalid{RESET}")
                print(f"  Expected: {expected_signature}")
                print(f"  Received: {signature}")
        else:
            print(f"{DIM}Signature:{RESET} {YELLOW}○ Not provided{RESET}")

        print(f"{DIM}Timestamp:{RESET} {timestamp or 'N/A'}")

        # Parse and display JSON
        print(f"\n{CYAN}Payload:{RESET}")
        try:
            data = json.loads(body.decode("utf-8"))
            self._print_payload(data)
        except json.JSONDecodeError as e:
            print(f"{RED}Invalid JSON: {e}{RESET}")
            print(body.decode("utf-8", errors="replace"))

        # Send response
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "received", "request_num": request_num}
        self.wfile.write(json.dumps(response).encode())

        print(f"{BLUE}{'─' * 80}{RESET}")
        print(f"{GREEN}Response: 200 OK{RESET}")

    def do_GET(self) -> None:
        """Handle GET requests (health check)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "status": "running",
            "service": "RAXE Webhook Test Server",
            "requests_received": WebhookHandler.request_count,
        }
        self.wfile.write(json.dumps(response).encode())

    def _compute_signature(self, timestamp: str, body: bytes) -> str:
        """Compute expected HMAC-SHA256 signature."""
        message = f"{timestamp}.".encode() + body
        signature = hmac.new(
            WebhookHandler.webhook_secret.encode(), message, hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def _print_payload(self, data: dict, indent: int = 2) -> None:
        """Pretty print the webhook payload with highlighting."""
        # Check for threat detection
        payload = data.get("payload", data)

        if payload.get("threat_detected"):
            severity = payload.get(
                "severity", payload.get("l1", {}).get("highest_severity", "unknown")
            )
            print(f"  {RED}{BOLD}⚠ THREAT DETECTED - Severity: {severity.upper()}{RESET}")

        # Print key fields with highlighting
        self._print_field("event_type", data.get("event_type"), indent)
        self._print_field("event_id", data.get("event_id"), indent)

        # MSSP context
        mssp_ctx = payload.get("_mssp_context", {})
        if mssp_ctx:
            print(f"  {YELLOW}_mssp_context:{RESET}")
            for k, v in mssp_ctx.items():
                print(f"    {k}: {v}")

        # MSSP data (sensitive - highlight)
        mssp_data = payload.get("_mssp_data", {})
        if mssp_data:
            print(f"  {RED}_mssp_data:{RESET} {DIM}(contains sensitive data){RESET}")
            for k, v in mssp_data.items():
                value_str = str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                print(f"    {k}: {value_str}")

        # Detection details
        if "l1" in payload:
            l1 = payload["l1"]
            if l1.get("hit"):
                print(f"  {CYAN}L1 Detections:{RESET}")
                for det in l1.get("detections", [])[:3]:
                    confidence = det.get("confidence", 0)
                    print(f"    - {det.get('rule_id')}: {det.get('severity')} ({confidence:.0%})")

        # Full JSON (collapsed unless --full-json)
        print(f"\n  {DIM}Full JSON:{RESET}")
        formatted = json.dumps(data, indent=2, default=str)
        lines = formatted.split("\n")
        if len(lines) > 30 and not WebhookHandler.full_json:
            for line in lines[:15]:
                print(f"  {DIM}{line}{RESET}")
            print(f"  {DIM}... ({len(lines) - 30} more lines) ...{RESET}")
            for line in lines[-15:]:
                print(f"  {DIM}{line}{RESET}")
            print(f"\n  {YELLOW}Tip: Use --full-json to see complete payload{RESET}")
        else:
            for line in lines:
                print(f"  {DIM}{line}{RESET}")

    def _print_field(self, name: str, value: object, indent: int) -> None:
        """Print a single field with formatting."""
        if value is not None:
            print(f"{'  ' * (indent // 2)}{name}: {value}")


def main() -> None:
    """Run the webhook test server."""
    parser = argparse.ArgumentParser(
        description="RAXE Webhook Test Server (HTTPS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=9001,
        help="Port to listen on (default: 9001)",
    )
    parser.add_argument(
        "--secret",
        "-s",
        default="test-secret",
        help="Webhook secret for signature verification (default: test-secret)",
    )
    parser.add_argument(
        "--cert-dir",
        default=os.path.join(tempfile.gettempdir(), "raxe-webhook-server"),
        help="Directory for SSL certificates (default: system temp dir)",
    )
    parser.add_argument(
        "--no-ssl",
        action="store_true",
        help="Disable HTTPS (use plain HTTP)",
    )
    parser.add_argument(
        "--full-json",
        action="store_true",
        help="Show full JSON payload without truncation",
    )
    args = parser.parse_args()

    WebhookHandler.webhook_secret = args.secret
    WebhookHandler.full_json = args.full_json

    # Ensure cert directory exists
    os.makedirs(args.cert_dir, exist_ok=True)

    server = HTTPServer(("0.0.0.0", args.port), WebhookHandler)

    protocol = "http"
    if not args.no_ssl:
        # Generate/load SSL certificate
        cert_file, key_file = generate_self_signed_cert(args.cert_dir)

        # Wrap socket with SSL
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"

    ssl_status = "Enabled (self-signed)" if not args.no_ssl else "Disabled"
    json_status = "Enabled" if args.full_json else "Disabled (use --full-json)"

    print(f"""
{BOLD}{BLUE}╔══════════════════════════════════════════════════════════════════════════════╗
║                       RAXE Webhook Test Server                               ║
╚══════════════════════════════════════════════════════════════════════════════╝{RESET}

{YELLOW}Listening on:{RESET} {protocol}://127.0.0.1:{args.port}
{YELLOW}Secret:{RESET}       {args.secret}
{YELLOW}SSL:{RESET}          {ssl_status}
{YELLOW}Full JSON:{RESET}    {json_status}

{CYAN}To configure RAXE MSSP:{RESET}
  raxe mssp create --id test_mssp --name "Test MSSP" \\
      --webhook-url {protocol}://127.0.0.1:{args.port}/raxe/alerts \\
      --webhook-secret {args.secret}

{CYAN}To test webhook (with self-signed cert):{RESET}
  RAXE_SKIP_SSL_VERIFY=true raxe mssp test-webhook test_mssp

{CYAN}To scan with MSSP context:{RESET}
  raxe customer create --mssp test_mssp --id test_cust --name "Test" --data-mode full
  RAXE_SKIP_SSL_VERIFY=true raxe scan "test prompt" --mssp test_mssp --customer test_cust

{DIM}Press Ctrl+C to stop{RESET}
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down...{RESET}")
        server.shutdown()
        print(f"{GREEN}Server stopped. Received {WebhookHandler.request_count} webhooks.{RESET}")


if __name__ == "__main__":
    main()
