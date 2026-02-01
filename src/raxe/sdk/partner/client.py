"""Partner API Client for MSSP ecosystem management.

Provides a high-level Python SDK for MSSPs to programmatically manage
customers, configure data policies, and monitor agents.

This client wraps the MSSP service layer to provide a clean API
for automation and integration scenarios.

Example:
    >>> from raxe.sdk.partner import PartnerClient
    >>> client = PartnerClient(mssp_id="mssp_yourcompany")
    >>>
    >>> # List customers
    >>> customers = client.list_customers()
    >>> print(f"Managing {len(customers)} customers")
    >>>
    >>> # Create a new customer
    >>> customer = client.create_customer(
    ...     customer_id="cust_acme",
    ...     name="Acme Corporation",
    ...     data_mode="full",
    ...     data_fields=["prompt", "matched_text"],
    ... )
    >>>
    >>> # Configure customer settings
    >>> client.configure_customer(
    ...     customer_id="cust_acme",
    ...     retention_days=60,
    ... )
    >>>
    >>> # List agents for a customer
    >>> agents = client.list_agents(customer_id="cust_acme")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raxe.application.mssp_service import (
    ConfigureCustomerRequest,
    CreateCustomerRequest,
    create_mssp_service,
)
from raxe.domain.mssp.models import DataMode, MSSPCustomer
from raxe.infrastructure.agent.registry import get_agent_registry


@dataclass
class PartnerClientConfig:
    """Configuration for Partner API client.

    Attributes:
        mssp_id: MSSP identifier (required)
        base_path: Override default MSSP data directory
        auto_create_mssp: If True, automatically create MSSP if not exists
    """

    mssp_id: str
    base_path: Path | None = None
    auto_create_mssp: bool = False


class PartnerClient:
    """Partner API client for MSSP ecosystem management.

    Provides methods for managing customers, configuring data policies,
    and monitoring agents within an MSSP context.

    Example:
        >>> client = PartnerClient(mssp_id="mssp_yourcompany")
        >>> customers = client.list_customers()
        >>> for c in customers:
        ...     print(f"{c.customer_id}: {c.name}")
    """

    def __init__(
        self,
        mssp_id: str,
        *,
        base_path: Path | str | None = None,
        config: PartnerClientConfig | None = None,
    ) -> None:
        """Initialize Partner API client.

        Args:
            mssp_id: MSSP identifier
            base_path: Override default MSSP data directory
            config: Client configuration (alternative to individual params)

        Raises:
            MSSPNotFoundError: If MSSP does not exist
        """
        if config:
            self._config = config
        else:
            self._config = PartnerClientConfig(
                mssp_id=mssp_id,
                base_path=Path(base_path) if base_path else None,
            )

        self._mssp_id = self._config.mssp_id
        self._service = create_mssp_service(base_path=self._config.base_path)

        # Verify MSSP exists
        self._mssp = self._service.get_mssp(self._mssp_id)

    @property
    def mssp_id(self) -> str:
        """Get MSSP identifier."""
        return self._mssp_id

    @property
    def mssp_name(self) -> str:
        """Get MSSP name."""
        return self._mssp.name

    # Customer Management
    # ===================

    def list_customers(self) -> list[MSSPCustomer]:
        """List all customers under this MSSP.

        Returns:
            List of MSSPCustomer objects

        Example:
            >>> customers = client.list_customers()
            >>> for c in customers:
            ...     print(f"{c.customer_id}: {c.name} ({c.data_mode.value})")
        """
        return self._service.list_customers(self._mssp_id)

    def get_customer(self, customer_id: str) -> MSSPCustomer:
        """Get a specific customer by ID.

        Args:
            customer_id: Customer identifier

        Returns:
            MSSPCustomer object

        Raises:
            CustomerNotFoundError: If customer not found
        """
        return self._service.get_customer(self._mssp_id, customer_id)

    def create_customer(
        self,
        customer_id: str,
        name: str,
        *,
        data_mode: str = "privacy_safe",
        data_fields: list[str] | None = None,
        retention_days: int = 30,
        heartbeat_threshold_seconds: int = 300,
    ) -> MSSPCustomer:
        """Create a new customer.

        Args:
            customer_id: Unique customer identifier (should start with 'cust_')
            name: Human-readable customer name
            data_mode: Privacy mode - 'full' or 'privacy_safe'
            data_fields: Fields to include in full mode (prompt, matched_text, etc.)
            retention_days: Data retention period (0-90 days)
            heartbeat_threshold_seconds: Agent offline detection threshold

        Returns:
            Created MSSPCustomer object

        Raises:
            DuplicateCustomerError: If customer already exists
            ValueError: If validation fails

        Example:
            >>> customer = client.create_customer(
            ...     customer_id="cust_acme",
            ...     name="Acme Corporation",
            ...     data_mode="full",
            ...     data_fields=["prompt", "matched_text"],
            ... )
        """
        mode = DataMode.FULL if data_mode == "full" else DataMode.PRIVACY_SAFE

        request = CreateCustomerRequest(
            customer_id=customer_id,
            mssp_id=self._mssp_id,
            name=name,
            data_mode=mode,
            data_fields=data_fields,
            retention_days=retention_days,
            heartbeat_threshold_seconds=heartbeat_threshold_seconds,
        )

        return self._service.create_customer(request)

    def configure_customer(
        self,
        customer_id: str,
        *,
        data_mode: str | None = None,
        data_fields: list[str] | None = None,
        retention_days: int | None = None,
        heartbeat_threshold_seconds: int | None = None,
    ) -> MSSPCustomer:
        """Configure an existing customer.

        Args:
            customer_id: Customer identifier
            data_mode: New privacy mode ('full' or 'privacy_safe')
            data_fields: New fields to include in full mode
            retention_days: New retention period (0-90)
            heartbeat_threshold_seconds: New agent offline threshold

        Returns:
            Updated MSSPCustomer object

        Raises:
            CustomerNotFoundError: If customer not found
            ValueError: If validation fails

        Example:
            >>> client.configure_customer(
            ...     customer_id="cust_acme",
            ...     data_mode="privacy_safe",
            ...     retention_days=60,
            ... )
        """
        mode = None
        if data_mode:
            mode = DataMode.FULL if data_mode == "full" else DataMode.PRIVACY_SAFE

        request = ConfigureCustomerRequest(
            customer_id=customer_id,
            mssp_id=self._mssp_id,
            data_mode=mode,
            data_fields=data_fields,
            retention_days=retention_days,
            heartbeat_threshold_seconds=heartbeat_threshold_seconds,
        )

        return self._service.configure_customer(request)

    def delete_customer(self, customer_id: str) -> None:
        """Delete a customer and all associated data.

        Args:
            customer_id: Customer identifier

        Raises:
            CustomerNotFoundError: If customer not found

        Example:
            >>> client.delete_customer("cust_old_customer")
        """
        self._service.delete_customer(self._mssp_id, customer_id)

    # Agent Management
    # ================

    def list_agents(
        self,
        customer_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List agents with current status.

        Args:
            customer_id: Filter by customer (optional)

        Returns:
            List of agent info dicts with status

        Example:
            >>> agents = client.list_agents(customer_id="cust_acme")
            >>> for a in agents:
            ...     print(f"{a['agent_id']}: {a['status']}")
        """
        registry = get_agent_registry()
        return registry.list_agents_with_status(
            mssp_id=self._mssp_id,
            customer_id=customer_id,
        )

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent details and status.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent info dict or None if not found

        Example:
            >>> agent = client.get_agent("agent_inst_123")
            >>> if agent:
            ...     print(f"Status: {agent['status']}")
        """
        registry = get_agent_registry()
        return registry.get_agent_with_status(agent_id)

    # Statistics
    # ==========

    def get_customer_stats(self, customer_id: str) -> dict[str, Any]:
        """Get statistics for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            Statistics dict with agent counts, scan counts, etc.

        Example:
            >>> stats = client.get_customer_stats("cust_acme")
            >>> print(f"Active agents: {stats['active_agents']}")
        """
        agents = self.list_agents(customer_id=customer_id)

        online_agents = sum(1 for a in agents if a.get("status") == "online")
        total_scans = sum(a.get("total_scans", 0) for a in agents)
        total_threats = sum(a.get("total_threats", 0) for a in agents)

        return {
            "customer_id": customer_id,
            "total_agents": len(agents),
            "online_agents": online_agents,
            "offline_agents": len(agents) - online_agents,
            "total_scans": total_scans,
            "total_threats": total_threats,
            "threat_rate": total_threats / total_scans if total_scans > 0 else 0,
        }

    def get_mssp_stats(self) -> dict[str, Any]:
        """Get aggregate statistics for the MSSP.

        Returns:
            Statistics dict with customer counts, agent counts, etc.

        Example:
            >>> stats = client.get_mssp_stats()
            >>> print(f"Total customers: {stats['total_customers']}")
        """
        customers = self.list_customers()
        all_agents = self.list_agents()

        online_agents = sum(1 for a in all_agents if a.get("status") == "online")
        total_scans = sum(a.get("total_scans", 0) for a in all_agents)
        total_threats = sum(a.get("total_threats", 0) for a in all_agents)

        return {
            "mssp_id": self._mssp_id,
            "mssp_name": self.mssp_name,
            "total_customers": len(customers),
            "total_agents": len(all_agents),
            "online_agents": online_agents,
            "offline_agents": len(all_agents) - online_agents,
            "total_scans": total_scans,
            "total_threats": total_threats,
            "threat_rate": total_threats / total_scans if total_scans > 0 else 0,
        }

    # Webhook Management
    # ==================

    def test_webhook(self) -> dict[str, Any]:
        """Test webhook connectivity.

        Returns:
            Test result dict with success status and details

        Example:
            >>> result = client.test_webhook()
            >>> if result['success']:
            ...     print("Webhook is working!")
        """
        import json
        import time

        import requests

        from raxe.infrastructure.webhooks.signing import WebhookSigner

        if not self._mssp.webhook_config:
            return {
                "success": False,
                "error": "No webhook configured for this MSSP",
            }

        webhook_url = self._mssp.webhook_config.url
        webhook_secret = self._mssp.webhook_config.secret

        # Build test payload
        test_payload = {
            "event_type": "test",
            "mssp_id": self._mssp_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": "Partner API webhook test",
        }

        # Sign and send
        body = json.dumps(test_payload).encode()
        signer = WebhookSigner(webhook_secret)
        headers = signer.get_signature_headers(body)
        headers["Content-Type"] = "application/json"

        try:
            response = requests.post(
                webhook_url,
                data=body,
                headers=headers,
                timeout=self._mssp.webhook_config.timeout_seconds,
            )

            return {
                "success": response.ok,
                "status_code": response.status_code,
                "webhook_url": webhook_url,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "webhook_url": webhook_url,
            }


def create_partner_client(
    mssp_id: str,
    *,
    base_path: Path | str | None = None,
) -> PartnerClient:
    """Factory function to create a Partner API client.

    Args:
        mssp_id: MSSP identifier
        base_path: Override default MSSP data directory

    Returns:
        PartnerClient instance

    Raises:
        MSSPNotFoundError: If MSSP does not exist

    Example:
        >>> from raxe.sdk.partner import create_partner_client
        >>> client = create_partner_client("mssp_yourcompany")
    """
    return PartnerClient(mssp_id=mssp_id, base_path=base_path)
