"""
Tests for webhook HMAC-SHA256 signature generation and verification.

These tests verify:
- Correct signature format (sha256=<hex>)
- Timestamp inclusion in signature computation
- Signature verification for valid requests
- Rejection of invalid secrets
- Replay attack protection via timestamp validation
- Tampered body detection
"""

import hashlib
import hmac
import time

import pytest

# Import paths for the module under test (will fail until implemented)
# Following the pattern from existing telemetry tests
try:
    from raxe.infrastructure.webhooks.signing import (
        WebhookSignatureError,
        WebhookSigner,
        generate_webhook_signature,
        verify_webhook_signature,
    )

    WEBHOOK_MODULE_AVAILABLE = True
except ImportError:
    WEBHOOK_MODULE_AVAILABLE = False
    WebhookSigner = None
    WebhookSignatureError = None
    generate_webhook_signature = None
    verify_webhook_signature = None

# Skip all tests if module not implemented yet
pytestmark = pytest.mark.skipif(
    not WEBHOOK_MODULE_AVAILABLE,
    reason="Webhook signing module not implemented yet",
)


class TestGenerateSignature:
    """Tests for webhook signature generation."""

    def test_generate_signature_format(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test that generated signature has correct format: sha256=<hex_signature>."""
        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        # Signature must start with 'sha256='
        assert signature.startswith(
            "sha256="
        ), f"Signature must start with 'sha256=', got: {signature}"

        # After prefix, must be valid hex string (64 chars for SHA-256)
        hex_part = signature[7:]
        assert len(hex_part) == 64, f"Hex part should be 64 chars, got {len(hex_part)}"
        assert all(c in "0123456789abcdef" for c in hex_part), "Signature must be lowercase hex"

    def test_signature_uses_timestamp_and_body(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test that signature computation uses both timestamp and body."""
        sig1 = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        # Different timestamp should produce different signature
        sig2 = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp + 1,
        )
        assert sig1 != sig2, "Different timestamps should produce different signatures"

        # Different body should produce different signature
        sig3 = generate_webhook_signature(
            body=b'{"different": "body"}',
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )
        assert sig1 != sig3, "Different body should produce different signatures"

    def test_signature_deterministic(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test that same inputs produce same signature."""
        sig1 = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )
        sig2 = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )
        assert sig1 == sig2, "Same inputs should produce identical signatures"

    def test_signature_uses_standard_hmac_sha256(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test that signature matches standard HMAC-SHA256 computation.

        The signed message format should be: {timestamp}.{body}
        This allows verification using standard HMAC libraries.
        """
        # Generate signature using our function
        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        # Compute expected signature manually
        signed_payload = f"{fixed_timestamp}.".encode() + sample_webhook_payload_json
        expected_sig = hmac.new(
            key=webhook_config.secret.encode("utf-8"),
            msg=signed_payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert signature == f"sha256={expected_sig}", "Signature should match manual HMAC-SHA256"


class TestVerifySignature:
    """Tests for webhook signature verification."""

    def test_verify_signature_valid(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test verification succeeds for valid signature."""
        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        # Should not raise any exception
        result = verify_webhook_signature(
            body=sample_webhook_payload_json,
            signature=signature,
            timestamp=fixed_timestamp,
            secret=webhook_config.secret,
        )
        assert result is True

    def test_verify_signature_invalid_secret(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test verification fails with wrong secret."""
        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        with pytest.raises(WebhookSignatureError, match="[Ss]ignature.*invalid|mismatch"):
            verify_webhook_signature(
                body=sample_webhook_payload_json,
                signature=signature,
                timestamp=fixed_timestamp,
                secret="wrong_secret_key",
            )

    def test_verify_signature_expired(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test verification rejects expired timestamps (replay protection).

        Signatures older than 5 minutes should be rejected to prevent
        replay attacks.
        """
        old_timestamp = int(time.time()) - 600  # 10 minutes ago

        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=old_timestamp,
        )

        with pytest.raises(WebhookSignatureError, match="[Ee]xpired|[Tt]imestamp.*old"):
            verify_webhook_signature(
                body=sample_webhook_payload_json,
                signature=signature,
                timestamp=old_timestamp,
                secret=webhook_config.secret,
                max_age_seconds=300,  # 5 minutes tolerance
            )

    def test_verify_signature_future_timestamp_rejected(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test verification rejects future timestamps."""
        future_timestamp = int(time.time()) + 600  # 10 minutes in the future

        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=future_timestamp,
        )

        with pytest.raises(WebhookSignatureError, match="[Ff]uture|[Tt]imestamp"):
            verify_webhook_signature(
                body=sample_webhook_payload_json,
                signature=signature,
                timestamp=future_timestamp,
                secret=webhook_config.secret,
                max_age_seconds=300,
            )

    def test_verify_signature_tampered_body(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test verification fails when body is tampered."""
        signature = generate_webhook_signature(
            body=sample_webhook_payload_json,
            secret=webhook_config.secret,
            timestamp=fixed_timestamp,
        )

        # Modify the body after signing
        tampered_body = sample_webhook_payload_json.replace(
            b"threat_detected", b"threat_detected_x"
        )

        with pytest.raises(WebhookSignatureError, match="[Ss]ignature.*invalid|mismatch"):
            verify_webhook_signature(
                body=tampered_body,
                signature=signature,
                timestamp=fixed_timestamp,
                secret=webhook_config.secret,
            )

    def test_verify_signature_invalid_format(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
        fixed_timestamp: int,
    ):
        """Test verification rejects signatures with invalid format."""
        # Missing sha256= prefix
        with pytest.raises(WebhookSignatureError, match="[Ff]ormat|[Pp]refix"):
            verify_webhook_signature(
                body=sample_webhook_payload_json,
                signature="abc123",
                timestamp=fixed_timestamp,
                secret=webhook_config.secret,
            )

        # Invalid hex
        with pytest.raises(WebhookSignatureError, match="[Hh]ex|[Ff]ormat"):
            verify_webhook_signature(
                body=sample_webhook_payload_json,
                signature="sha256=not_valid_hex_zzz",
                timestamp=fixed_timestamp,
                secret=webhook_config.secret,
            )


class TestWebhookSigner:
    """Tests for WebhookSigner class (higher-level API)."""

    def test_signer_initialization(self, webhook_config):
        """Test WebhookSigner initializes correctly."""
        signer = WebhookSigner(secret=webhook_config.secret)
        assert signer.secret == webhook_config.secret

    def test_signer_sign_and_verify_roundtrip(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test signing and verification round-trip."""
        signer = WebhookSigner(secret=webhook_config.secret)

        # Sign
        timestamp, signature = signer.sign(sample_webhook_payload_json)

        # Verify
        assert signer.verify(
            body=sample_webhook_payload_json,
            signature=signature,
            timestamp=timestamp,
        )

    def test_signer_generates_current_timestamp(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test that signer generates a timestamp close to current time."""
        signer = WebhookSigner(secret=webhook_config.secret)

        current_time = int(time.time())
        timestamp, _ = signer.sign(sample_webhook_payload_json)

        # Should be within 1 second of current time
        assert abs(timestamp - current_time) <= 1

    def test_signer_headers_format(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test that signer produces correctly named headers."""
        signer = WebhookSigner(secret=webhook_config.secret)

        headers = signer.get_signature_headers(sample_webhook_payload_json)

        # Should include both required headers
        assert "X-RAXE-Signature" in headers
        assert "X-RAXE-Timestamp" in headers

        # Signature should be in correct format
        assert headers["X-RAXE-Signature"].startswith("sha256=")

        # Timestamp should be numeric string
        assert headers["X-RAXE-Timestamp"].isdigit()

    def test_signer_verify_headers(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test verification using headers dict."""
        signer = WebhookSigner(secret=webhook_config.secret)

        headers = signer.get_signature_headers(sample_webhook_payload_json)

        # Should be able to verify using the headers
        assert signer.verify_from_headers(
            body=sample_webhook_payload_json,
            headers=headers,
        )

    def test_signer_verify_missing_headers(
        self,
        webhook_config,
        sample_webhook_payload_json: bytes,
    ):
        """Test verification fails gracefully with missing headers."""
        signer = WebhookSigner(secret=webhook_config.secret)

        with pytest.raises(WebhookSignatureError, match="[Mm]issing.*header|[Hh]eader.*required"):
            signer.verify_from_headers(
                body=sample_webhook_payload_json,
                headers={},  # No headers
            )

        with pytest.raises(WebhookSignatureError, match="[Mm]issing.*header|[Hh]eader.*required"):
            signer.verify_from_headers(
                body=sample_webhook_payload_json,
                headers={"X-RAXE-Signature": "sha256=abc"},  # Missing timestamp
            )
