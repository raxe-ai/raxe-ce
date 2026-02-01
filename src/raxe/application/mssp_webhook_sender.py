"""MSSP Webhook Sender for dual-send telemetry.

Responsible for:
1. Sending telemetry to MSSP webhooks when configured
2. Respecting data_mode (full vs privacy_safe)
3. Never blocking RAXE telemetry on MSSP webhook failures
4. Caching webhook services per MSSP for efficiency

This module implements the "dual-send" pattern:
- RAXE platform receives metadata-only (privacy-safe)
- MSSP receives full data if enabled (per-customer configuration)
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

from raxe.application.mssp_service import create_mssp_service
from raxe.domain.mssp.models import DataMode
from raxe.infrastructure.audit.mssp_audit_logger import log_mssp_delivery
from raxe.infrastructure.mssp.yaml_repository import (
    CustomerNotFoundError,
    MSSPNotFoundError,
)
from raxe.infrastructure.webhooks.delivery import (
    WebhookDeliveryService,
    WebhookRetryPolicy,
)

if TYPE_CHECKING:
    from raxe.application.mssp_service import MSSPService
    from raxe.domain.mssp.models import MSSPCustomer, WebhookConfig

logger = logging.getLogger(__name__)


class MSSPWebhookSender:
    """Sends telemetry events to MSSP webhooks.

    Handles the MSSP side of dual-send telemetry:
    - Looks up MSSP and customer configuration
    - Respects data_mode (full vs privacy_safe)
    - Delivers via WebhookDeliveryService with retries
    - Never blocks or raises on failures (non-blocking design)

    Example:
        >>> sender = MSSPWebhookSender()
        >>> result = sender.send_if_configured(
        ...     event_payload={"event_type": "scan", "payload": {...}},
        ...     mssp_id="mssp_partner",
        ...     customer_id="cust_acme",
        ... )
        >>> print(result)  # True if sent or not configured, False on failure
        True
    """

    def __init__(self, mssp_service: MSSPService | None = None) -> None:
        """Initialize MSSP webhook sender.

        Args:
            mssp_service: Optional MSSP service instance (lazy-loaded if None)
        """
        self._mssp_service = mssp_service
        self._webhook_cache: dict[str, WebhookDeliveryService] = {}

    @property
    def mssp_service(self) -> MSSPService:
        """Lazy-load MSSP service."""
        if self._mssp_service is None:
            self._mssp_service = create_mssp_service()
        return self._mssp_service

    def send_if_configured(
        self,
        event_payload: dict[str, Any],
        mssp_id: str | None,
        customer_id: str | None,
    ) -> bool:
        """Send event to MSSP webhook if configured.

        This method is designed to be non-blocking:
        - Returns True if event was sent successfully or not configured
        - Returns False if delivery failed (but never raises)

        Args:
            event_payload: Full event payload (will be filtered by data_mode)
            mssp_id: MSSP identifier (None = skip)
            customer_id: Customer identifier (None = skip)

        Returns:
            True if sent successfully or not configured (skip)
            False if delivery failed
        """
        # Skip if not configured for MSSP telemetry
        if not mssp_id:
            return True
        if not customer_id:
            return True

        try:
            return self._send_to_mssp(event_payload, mssp_id, customer_id)
        except Exception as e:
            # Never block RAXE telemetry on MSSP webhook errors
            logger.warning(
                "MSSP webhook send failed",
                extra={
                    "mssp_id": mssp_id,
                    "customer_id": customer_id,
                    "error": str(e),
                },
            )
            return False

    def _send_to_mssp(
        self,
        event_payload: dict[str, Any],
        mssp_id: str,
        customer_id: str,
    ) -> bool:
        """Internal method to send event to MSSP.

        Args:
            event_payload: Event payload
            mssp_id: MSSP identifier
            customer_id: Customer identifier

        Returns:
            True if sent or not configured, False if failed
        """
        # Get MSSP configuration
        try:
            mssp = self.mssp_service.get_mssp(mssp_id)
        except MSSPNotFoundError:
            # MSSP not found - graceful skip (not an error)
            logger.debug(f"MSSP '{mssp_id}' not found, skipping webhook")
            return True

        # Get customer configuration
        try:
            customer = self.mssp_service.get_customer(mssp_id, customer_id)
        except CustomerNotFoundError:
            # Customer not found - graceful skip
            logger.debug(f"Customer '{customer_id}' not found, skipping webhook")
            return True

        # Determine webhook config (customer override or MSSP default)
        webhook_config = customer.webhook_config or mssp.webhook_config

        if not webhook_config:
            # No webhook configured - graceful skip
            return True

        # Prepare payload based on data_mode
        delivery_payload = self._prepare_payload(event_payload, customer)

        # Get or create webhook service
        webhook_service = self._get_or_create_webhook_service(mssp_id, webhook_config)

        # Deliver
        result = webhook_service.deliver(delivery_payload)

        # Extract event_id and data_fields for audit
        event_id = None
        data_fields_sent: list[str] = []
        if "payload" in delivery_payload:
            inner = delivery_payload["payload"]
            # Get data_fields from _mssp_context
            ctx = inner.get("_mssp_context", {})
            data_fields_sent = ctx.get("data_fields", [])
            # If _mssp_data exists, note what fields were actually sent
            mssp_data = inner.get("_mssp_data", {})
            if mssp_data:
                data_fields_sent = list(mssp_data.keys())

        # Log audit trail
        try:
            log_mssp_delivery(
                mssp_id=mssp_id,
                customer_id=customer_id,
                data_mode=customer.data_mode.value,
                data_fields_sent=data_fields_sent,
                delivery_status="success" if result.success else "failed",
                event_id=event_id,
                http_status_code=result.status_code,
                error_message=result.error_message,
                attempts=result.attempts,
                destination_url=webhook_config.url,
            )
        except Exception as audit_err:
            # Never let audit logging block webhook delivery
            logger.debug(f"Audit logging failed: {audit_err}")

        if result.success:
            logger.debug(
                "MSSP webhook delivered",
                extra={
                    "mssp_id": mssp_id,
                    "customer_id": customer_id,
                    "attempts": result.attempts,
                },
            )
            return True
        else:
            logger.warning(
                "MSSP webhook delivery failed",
                extra={
                    "mssp_id": mssp_id,
                    "customer_id": customer_id,
                    "attempts": result.attempts,
                    "error": result.error_message,
                },
            )
            return False

    def _prepare_payload(
        self,
        event_payload: dict[str, Any],
        customer: MSSPCustomer,
    ) -> dict[str, Any]:
        """Prepare payload based on customer data_mode.

        Args:
            event_payload: Original event payload
            customer: Customer configuration

        Returns:
            Filtered payload based on data_mode
        """
        # Deep copy to avoid modifying original
        payload = copy.deepcopy(event_payload)

        # Handle privacy_safe mode - strip _mssp_data
        if customer.data_mode == DataMode.PRIVACY_SAFE:
            # Remove sensitive data block
            if "payload" in payload and "_mssp_data" in payload["payload"]:
                del payload["payload"]["_mssp_data"]

        # For full mode, keep everything including _mssp_data

        return payload

    def _get_or_create_webhook_service(
        self,
        mssp_id: str,
        webhook_config: WebhookConfig,
    ) -> WebhookDeliveryService:
        """Get cached webhook service or create new one.

        Args:
            mssp_id: MSSP identifier (cache key)
            webhook_config: Webhook configuration

        Returns:
            WebhookDeliveryService instance
        """
        if mssp_id not in self._webhook_cache:
            # Create with reasonable defaults for MSSP delivery
            self._webhook_cache[mssp_id] = WebhookDeliveryService(
                endpoint=webhook_config.url,
                secret=webhook_config.secret,
                timeout_seconds=10,
                retry_policy=WebhookRetryPolicy(
                    max_retries=3,
                    initial_delay_ms=500,
                    max_delay_ms=5000,
                ),
            )

        return self._webhook_cache[mssp_id]


# Factory function
def create_mssp_webhook_sender(
    mssp_service: MSSPService | None = None,
) -> MSSPWebhookSender:
    """Create an MSSP webhook sender.

    Args:
        mssp_service: Optional MSSP service instance

    Returns:
        MSSPWebhookSender instance
    """
    return MSSPWebhookSender(mssp_service)


__all__ = [
    "MSSPWebhookSender",
    "create_mssp_webhook_sender",
]
