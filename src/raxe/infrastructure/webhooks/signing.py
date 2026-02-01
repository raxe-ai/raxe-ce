"""
Webhook HMAC-SHA256 signature generation and verification.

This module provides cryptographic signing for webhook payloads to ensure:
- Authenticity: Requests originate from RAXE
- Integrity: Payload has not been tampered with
- Replay protection: Signatures expire after configurable time window

Signature format follows industry standard: sha256={hex_hmac}
Signed payload format: {timestamp}.{body}
"""

import hashlib
import hmac
import time


class WebhookSignatureError(Exception):
    """Error raised when webhook signature validation fails.

    This exception indicates one of:
    - Invalid signature format (missing sha256= prefix)
    - Signature mismatch (wrong secret or tampered body)
    - Expired timestamp (replay attack protection)
    - Future timestamp (clock skew protection)
    """

    pass


def generate_webhook_signature(
    body: bytes,
    secret: str,
    timestamp: int,
) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.

    The signature is computed over the concatenation of timestamp and body,
    allowing receivers to verify both the content and timing of the request.

    Args:
        body: Raw webhook payload bytes (typically JSON)
        secret: Shared HMAC secret key
        timestamp: Unix timestamp when signature was created

    Returns:
        Signature string in format: sha256={64_hex_chars}

    Example:
        >>> sig = generate_webhook_signature(b'{"event": "test"}', "secret", 1706526600)
        >>> sig.startswith("sha256=")
        True
        >>> len(sig)  # sha256= (7) + 64 hex chars
        71
    """
    # Construct signed payload: {timestamp}.{body}
    signed_payload = f"{timestamp}.".encode() + body

    # Compute HMAC-SHA256
    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return f"sha256={signature}"


def verify_webhook_signature(
    body: bytes,
    signature: str,
    timestamp: int,
    secret: str,
    max_age_seconds: int | None = None,
) -> bool:
    """Verify webhook signature and optionally timestamp validity.

    Performs up to three validations:
    1. Signature format is valid (sha256= prefix, valid hex)
    2. Computed signature matches provided signature
    3. If max_age_seconds provided: Timestamp is within acceptable window

    Args:
        body: Raw webhook payload bytes
        signature: Signature to verify (format: sha256={hex})
        timestamp: Unix timestamp from request
        secret: Shared HMAC secret key
        max_age_seconds: Maximum age of signature in seconds. If None (default),
            timestamp validation is skipped. Set to 300 (5 minutes) for
            replay attack protection.

    Returns:
        True if signature is valid

    Raises:
        WebhookSignatureError: If signature validation fails

    Example:
        >>> sig = generate_webhook_signature(b'{"test": 1}', "secret", int(time.time()))
        >>> verify_webhook_signature(b'{"test": 1}', sig, int(time.time()), "secret")
        True
    """
    # Validate signature format
    if not signature.startswith("sha256="):
        raise WebhookSignatureError("Invalid signature format: missing 'sha256=' prefix")

    hex_part = signature[7:]  # Remove "sha256=" prefix

    # Validate hex string
    if not all(c in "0123456789abcdef" for c in hex_part.lower()):
        raise WebhookSignatureError(
            "Invalid signature format: hex portion contains invalid characters"
        )

    # Check timestamp validity only if max_age_seconds is specified
    if max_age_seconds is not None:
        current_time = int(time.time())

        # Reject future timestamps (with small tolerance for clock skew)
        if timestamp > current_time + 60:  # 60 second tolerance for clock skew
            raise WebhookSignatureError(f"Timestamp is in the future: {timestamp} > {current_time}")

        # Reject expired timestamps
        age = current_time - timestamp
        if age > max_age_seconds:
            raise WebhookSignatureError(
                f"Timestamp expired: signature is {age}s old, max allowed is {max_age_seconds}s"
            )

    # Compute expected signature
    expected_signature = generate_webhook_signature(body, secret, timestamp)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        raise WebhookSignatureError(
            "Signature mismatch: computed signature does not match provided signature"
        )

    return True


class WebhookSigner:
    """High-level API for webhook signature operations.

    Provides convenient methods for both signing and verifying webhooks,
    including header generation and extraction.

    Attributes:
        secret: The HMAC secret key used for signing

    Example:
        >>> signer = WebhookSigner("my_secret_key")
        >>> headers = signer.get_signature_headers(b'{"event": "test"}')
        >>> print(headers.keys())
        dict_keys(['X-RAXE-Signature', 'X-RAXE-Timestamp'])
    """

    # Header names for webhook signatures
    SIGNATURE_HEADER = "X-RAXE-Signature"
    TIMESTAMP_HEADER = "X-RAXE-Timestamp"

    def __init__(self, secret: str) -> None:
        """Initialize signer with shared secret.

        Args:
            secret: HMAC secret key for signing/verification
        """
        self.secret = secret

    def sign(self, body: bytes) -> tuple[int, str]:
        """Sign a webhook payload.

        Generates a timestamp and computes the signature.

        Args:
            body: Raw payload bytes to sign

        Returns:
            Tuple of (timestamp, signature)
        """
        timestamp = int(time.time())
        signature = generate_webhook_signature(body, self.secret, timestamp)
        return timestamp, signature

    def verify(
        self,
        body: bytes,
        signature: str,
        timestamp: int,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify a webhook signature.

        Args:
            body: Raw payload bytes
            signature: Signature to verify
            timestamp: Unix timestamp from request
            max_age_seconds: Maximum signature age (default: 5 minutes)

        Returns:
            True if valid

        Raises:
            WebhookSignatureError: If validation fails
        """
        return verify_webhook_signature(
            body=body,
            signature=signature,
            timestamp=timestamp,
            secret=self.secret,
            max_age_seconds=max_age_seconds,
        )

    def get_signature_headers(self, body: bytes) -> dict[str, str]:
        """Generate HTTP headers for signed webhook request.

        Creates the required signature and timestamp headers that should
        be included in outgoing webhook requests.

        Args:
            body: Raw payload bytes to sign

        Returns:
            Dict with X-RAXE-Signature and X-RAXE-Timestamp headers
        """
        timestamp, signature = self.sign(body)
        return {
            self.SIGNATURE_HEADER: signature,
            self.TIMESTAMP_HEADER: str(timestamp),
        }

    def verify_from_headers(
        self,
        body: bytes,
        headers: dict[str, str],
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify webhook signature from HTTP headers.

        Extracts signature and timestamp from headers and validates.

        Args:
            body: Raw payload bytes
            headers: HTTP headers dict (case-sensitive keys)
            max_age_seconds: Maximum signature age (default: 5 minutes)

        Returns:
            True if valid

        Raises:
            WebhookSignatureError: If headers missing or validation fails
        """
        # Check for required headers (case-insensitive lookup)
        signature = None
        timestamp_str = None

        for key, value in headers.items():
            if key.lower() == self.SIGNATURE_HEADER.lower():
                signature = value
            elif key.lower() == self.TIMESTAMP_HEADER.lower():
                timestamp_str = value

        if signature is None:
            raise WebhookSignatureError(f"Missing required header: {self.SIGNATURE_HEADER}")

        if timestamp_str is None:
            raise WebhookSignatureError(f"Missing required header: {self.TIMESTAMP_HEADER}")

        try:
            timestamp = int(timestamp_str)
        except ValueError as e:
            raise WebhookSignatureError(f"Invalid timestamp header value: {timestamp_str}") from e

        return self.verify(
            body=body,
            signature=signature,
            timestamp=timestamp,
            max_age_seconds=max_age_seconds,
        )
