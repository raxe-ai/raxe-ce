"""
Webhook infrastructure for MSSP integration.

This package provides webhook delivery capabilities for sending real-time
security alerts to MSSP (Managed Security Service Provider) endpoints.

Features:
- HMAC-SHA256 signature authentication
- Exponential backoff retry with jitter
- Circuit breaker for cascade failure prevention
- Replay attack protection via timestamp validation

Modules:
- signing: Cryptographic signature generation and verification
- delivery: HTTP delivery service with retry and circuit breaker

Example:
    >>> from raxe.infrastructure.webhooks import (
    ...     WebhookDeliveryService,
    ...     WebhookRetryPolicy,
    ... )
    >>>
    >>> service = WebhookDeliveryService(
    ...     endpoint="https://mssp.example.com/webhooks",
    ...     secret="whsec_your_secret_key",
    ... )
    >>> result = service.deliver({"event": "threat_detected"})
    >>> print(result.success)
    True
"""

from raxe.infrastructure.webhooks.delivery import (
    WebhookDeliveryError,
    WebhookDeliveryResult,
    WebhookDeliveryService,
    WebhookRetryPolicy,
)
from raxe.infrastructure.webhooks.signing import (
    WebhookSignatureError,
    WebhookSigner,
    generate_webhook_signature,
    verify_webhook_signature,
)

__all__ = [
    "WebhookDeliveryError",
    "WebhookDeliveryResult",
    "WebhookDeliveryService",
    "WebhookRetryPolicy",
    "WebhookSignatureError",
    "WebhookSigner",
    "generate_webhook_signature",
    "verify_webhook_signature",
]
