"""Application service for MSSP/Partner ecosystem management.

Provides business logic for managing MSSPs, customers, and agents.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from raxe.domain.mssp.models import (
    MSSP,
    DataMode,
    MSSPCustomer,
    MSSPTier,
    WebhookConfig,
)
from raxe.infrastructure.mssp import (
    get_customer_repo,
    get_mssp_base_path,
    get_mssp_repo,
)
from raxe.infrastructure.mssp.yaml_repository import (
    CustomerNotFoundError,
    DuplicateCustomerError,
    DuplicateMSSPError,
    MSSPNotFoundError,
)

if TYPE_CHECKING:
    pass


@dataclass
class CreateMSSPRequest:
    """Request to create a new MSSP."""

    mssp_id: str
    name: str
    webhook_url: str
    webhook_secret: str
    tier: MSSPTier = MSSPTier.STARTER
    max_customers: int | None = None  # None = use tier default

    def __post_init__(self) -> None:
        """Apply tier default for max_customers if not explicitly set."""
        if self.max_customers is None:
            object.__setattr__(self, "max_customers", self.tier.default_max_customers)


@dataclass
class CreateCustomerRequest:
    """Request to create a new customer."""

    customer_id: str
    mssp_id: str
    name: str
    data_mode: DataMode = DataMode.PRIVACY_SAFE
    data_fields: list[str] | None = None
    retention_days: int = 30
    heartbeat_threshold_seconds: int = 300


@dataclass
class ConfigureCustomerRequest:
    """Request to configure an existing customer."""

    customer_id: str
    mssp_id: str
    data_mode: DataMode | None = None
    data_fields: list[str] | None = None
    retention_days: int | None = None
    heartbeat_threshold_seconds: int | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None


class MSSPService:
    """Service for managing MSSPs and their customers."""

    def __init__(self, base_path: Path | None = None):
        """Initialize service.

        Args:
            base_path: Optional custom base path for storage
        """
        self.base_path = base_path or get_mssp_base_path()
        self._mssp_repo = get_mssp_repo(self.base_path)

    def _hash_api_key(self, secret: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(secret.encode()).hexdigest()

    # ==================== MSSP Operations ====================

    def create_mssp(self, request: CreateMSSPRequest) -> MSSP:
        """Create a new MSSP.

        Args:
            request: MSSP creation request

        Returns:
            Created MSSP

        Raises:
            DuplicateMSSPError: If MSSP already exists
            ValueError: If validation fails
        """
        # Validate mssp_id format
        if not request.mssp_id.startswith("mssp_"):
            raise ValueError("mssp_id must start with 'mssp_'")

        # Create webhook config
        webhook_config = WebhookConfig(
            url=request.webhook_url,
            secret=request.webhook_secret,
        )

        # Create MSSP entity
        mssp = MSSP(
            mssp_id=request.mssp_id,
            name=request.name,
            tier=request.tier,
            max_customers=request.max_customers,
            api_key_hash=self._hash_api_key(request.webhook_secret),
            webhook_config=webhook_config,
        )

        return self._mssp_repo.create(mssp)

    def get_mssp(self, mssp_id: str) -> MSSP:
        """Get an MSSP by ID.

        Args:
            mssp_id: MSSP identifier

        Returns:
            MSSP entity

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        return self._mssp_repo.get(mssp_id)

    def list_mssps(self) -> list[MSSP]:
        """List all MSSPs.

        Returns:
            List of MSSP entities
        """
        return self._mssp_repo.list()

    def delete_mssp(self, mssp_id: str) -> None:
        """Delete an MSSP and all its data.

        Args:
            mssp_id: MSSP identifier

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        self._mssp_repo.delete(mssp_id)

    def mssp_exists(self, mssp_id: str) -> bool:
        """Check if MSSP exists.

        Args:
            mssp_id: MSSP identifier

        Returns:
            True if exists
        """
        return self._mssp_repo.exists(mssp_id)

    # ==================== Customer Operations ====================

    def create_customer(self, request: CreateCustomerRequest) -> MSSPCustomer:
        """Create a new customer under an MSSP.

        Args:
            request: Customer creation request

        Returns:
            Created customer

        Raises:
            MSSPNotFoundError: If MSSP not found
            DuplicateCustomerError: If customer already exists
            ValueError: If validation fails
        """
        # Verify MSSP exists
        mssp = self._mssp_repo.get(request.mssp_id)

        # Validate customer_id format
        if not request.customer_id.startswith("cust_"):
            raise ValueError("customer_id must start with 'cust_'")

        # Check customer limit for MSSP tier
        customer_repo = get_customer_repo(request.mssp_id, self.base_path)
        current_count = len(customer_repo.list())
        if mssp.max_customers > 0 and current_count >= mssp.max_customers:
            raise ValueError(
                f"Customer limit reached ({mssp.max_customers}) for MSSP tier "
                f"'{mssp.tier.value}'. Upgrade tier to add more customers."
            )

        # Create customer entity
        customer = MSSPCustomer(
            customer_id=request.customer_id,
            mssp_id=request.mssp_id,
            name=request.name,
            data_mode=request.data_mode,
            data_fields=request.data_fields or [],
            retention_days=request.retention_days,
            heartbeat_threshold_seconds=request.heartbeat_threshold_seconds,
        )

        return customer_repo.create(customer)

    def get_customer(self, mssp_id: str, customer_id: str) -> MSSPCustomer:
        """Get a customer by ID.

        Args:
            mssp_id: MSSP identifier
            customer_id: Customer identifier

        Returns:
            Customer entity

        Raises:
            MSSPNotFoundError: If MSSP not found
            CustomerNotFoundError: If customer not found
        """
        # Verify MSSP exists
        if not self._mssp_repo.exists(mssp_id):
            raise MSSPNotFoundError(mssp_id)

        customer_repo = get_customer_repo(mssp_id, self.base_path)
        return customer_repo.get(customer_id)

    def list_customers(self, mssp_id: str) -> list[MSSPCustomer]:
        """List all customers for an MSSP.

        Args:
            mssp_id: MSSP identifier

        Returns:
            List of customer entities

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        # Verify MSSP exists
        if not self._mssp_repo.exists(mssp_id):
            raise MSSPNotFoundError(mssp_id)

        customer_repo = get_customer_repo(mssp_id, self.base_path)
        return customer_repo.list()

    def configure_customer(self, request: ConfigureCustomerRequest) -> MSSPCustomer:
        """Configure an existing customer.

        Args:
            request: Customer configuration request

        Returns:
            Updated customer

        Raises:
            MSSPNotFoundError: If MSSP not found
            CustomerNotFoundError: If customer not found
        """
        # Verify MSSP exists
        if not self._mssp_repo.exists(request.mssp_id):
            raise MSSPNotFoundError(request.mssp_id)

        customer_repo = get_customer_repo(request.mssp_id, self.base_path)
        existing = customer_repo.get(request.customer_id)

        # Build updated customer
        webhook_config = existing.webhook_config
        if request.webhook_url and request.webhook_secret:
            webhook_config = WebhookConfig(
                url=request.webhook_url,
                secret=request.webhook_secret,
            )

        # Build updated customer with request values or existing as fallback
        new_data_mode = request.data_mode if request.data_mode else existing.data_mode
        new_data_fields = (
            request.data_fields if request.data_fields is not None else existing.data_fields
        )
        new_retention = (
            request.retention_days
            if request.retention_days is not None
            else existing.retention_days
        )
        new_heartbeat = (
            request.heartbeat_threshold_seconds
            if request.heartbeat_threshold_seconds is not None
            else existing.heartbeat_threshold_seconds
        )

        updated = MSSPCustomer(
            customer_id=existing.customer_id,
            mssp_id=existing.mssp_id,
            name=existing.name,
            data_mode=new_data_mode,
            data_fields=new_data_fields,
            retention_days=new_retention,
            heartbeat_threshold_seconds=new_heartbeat,
            webhook_config=webhook_config,
            created_at=existing.created_at,
        )

        return customer_repo.update(updated)

    def delete_customer(self, mssp_id: str, customer_id: str) -> None:
        """Delete a customer.

        Args:
            mssp_id: MSSP identifier
            customer_id: Customer identifier

        Raises:
            MSSPNotFoundError: If MSSP not found
            CustomerNotFoundError: If customer not found
        """
        # Verify MSSP exists
        if not self._mssp_repo.exists(mssp_id):
            raise MSSPNotFoundError(mssp_id)

        customer_repo = get_customer_repo(mssp_id, self.base_path)
        customer_repo.delete(customer_id)


def create_mssp_service(base_path: Path | None = None) -> MSSPService:
    """Factory function to create an MSSP service.

    Args:
        base_path: Optional custom base path for storage

    Returns:
        MSSPService instance
    """
    return MSSPService(base_path)


# Re-export exceptions for convenience
__all__ = [
    "ConfigureCustomerRequest",
    "CreateCustomerRequest",
    "CreateMSSPRequest",
    "CustomerNotFoundError",
    "DuplicateCustomerError",
    "DuplicateMSSPError",
    "MSSPNotFoundError",
    "MSSPService",
    "create_mssp_service",
]
