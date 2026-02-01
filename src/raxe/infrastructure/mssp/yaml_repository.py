"""YAML-based repository implementations for MSSP/Partner ecosystem.

Provides persistent storage for MSSP and Customer entities using YAML files.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from raxe.domain.mssp.models import (
    MSSP,
    DataMode,
    MSSPCustomer,
    MSSPTier,
    WebhookConfig,
)

if TYPE_CHECKING:
    pass


class MSSPNotFoundError(Exception):
    """Raised when an MSSP is not found."""

    def __init__(self, mssp_id: str):
        self.mssp_id = mssp_id
        super().__init__(f"MSSP '{mssp_id}' not found")


class CustomerNotFoundError(Exception):
    """Raised when a customer is not found."""

    def __init__(self, customer_id: str, mssp_id: str):
        self.customer_id = customer_id
        self.mssp_id = mssp_id
        super().__init__(f"Customer '{customer_id}' not found in MSSP '{mssp_id}'")


class DuplicateMSSPError(Exception):
    """Raised when trying to create a duplicate MSSP."""

    def __init__(self, mssp_id: str):
        self.mssp_id = mssp_id
        super().__init__(f"MSSP '{mssp_id}' already exists")


class DuplicateCustomerError(Exception):
    """Raised when trying to create a duplicate customer."""

    def __init__(self, customer_id: str, mssp_id: str):
        self.customer_id = customer_id
        self.mssp_id = mssp_id
        super().__init__(f"Customer '{customer_id}' already exists in MSSP '{mssp_id}'")


def _now_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class YamlMSSPRepository:
    """YAML-based storage for MSSP entities.

    Storage structure:
        {base_path}/{mssp_id}/mssp.yaml - MSSP configuration
        {base_path}/{mssp_id}/customers/ - Customer configurations
    """

    def __init__(self, base_path: Path):
        """Initialize repository.

        Args:
            base_path: Base path for MSSP storage
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _mssp_path(self, mssp_id: str) -> Path:
        """Get path to MSSP directory."""
        return self.base_path / mssp_id

    def _mssp_config_path(self, mssp_id: str) -> Path:
        """Get path to MSSP config file."""
        return self._mssp_path(mssp_id) / "mssp.yaml"

    def exists(self, mssp_id: str) -> bool:
        """Check if MSSP exists."""
        return self._mssp_config_path(mssp_id).exists()

    def create(self, mssp: MSSP) -> MSSP:
        """Create a new MSSP.

        Args:
            mssp: MSSP entity to create

        Returns:
            Created MSSP with timestamps

        Raises:
            DuplicateMSSPError: If MSSP already exists
        """
        if self.exists(mssp.mssp_id):
            raise DuplicateMSSPError(mssp.mssp_id)

        # Create directory structure
        mssp_path = self._mssp_path(mssp.mssp_id)
        mssp_path.mkdir(parents=True, exist_ok=True)
        (mssp_path / "customers").mkdir(exist_ok=True)

        # Set timestamps
        now = _now_iso()
        data = asdict(mssp)
        data["created_at"] = now
        data["updated_at"] = now

        # Handle webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = asdict(mssp.webhook_config) if mssp.webhook_config else None

        # Convert tier enum to string
        data["tier"] = mssp.tier.value

        # Write config
        config_path = self._mssp_config_path(mssp.mssp_id)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        return self.get(mssp.mssp_id)

    def get(self, mssp_id: str) -> MSSP:
        """Get an MSSP by ID.

        Args:
            mssp_id: MSSP identifier

        Returns:
            MSSP entity

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        config_path = self._mssp_config_path(mssp_id)
        if not config_path.exists():
            raise MSSPNotFoundError(mssp_id)

        with open(config_path) as f:
            data = yaml.safe_load(f)

        # Convert tier string to enum
        data["tier"] = MSSPTier(data["tier"])

        # Reconstruct webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = WebhookConfig(**data["webhook_config"])

        return MSSP(**data)

    def list(self) -> list[MSSP]:
        """List all MSSPs.

        Returns:
            List of MSSP entities
        """
        mssps = []
        if not self.base_path.exists():
            return mssps

        for mssp_dir in self.base_path.iterdir():
            if mssp_dir.is_dir() and (mssp_dir / "mssp.yaml").exists():
                try:
                    mssps.append(self.get(mssp_dir.name))
                except Exception:  # noqa: S110
                    pass  # Skip invalid entries

        return mssps

    def update(self, mssp: MSSP) -> MSSP:
        """Update an existing MSSP.

        Args:
            mssp: MSSP entity with updated values

        Returns:
            Updated MSSP

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        if not self.exists(mssp.mssp_id):
            raise MSSPNotFoundError(mssp.mssp_id)

        # Get existing for created_at
        existing = self.get(mssp.mssp_id)

        # Prepare data
        data = asdict(mssp)
        data["created_at"] = existing.created_at
        data["updated_at"] = _now_iso()

        # Handle webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = asdict(mssp.webhook_config) if mssp.webhook_config else None

        # Convert tier enum to string
        data["tier"] = mssp.tier.value

        # Write config
        config_path = self._mssp_config_path(mssp.mssp_id)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        return self.get(mssp.mssp_id)

    def delete(self, mssp_id: str) -> None:
        """Delete an MSSP and all its data.

        Args:
            mssp_id: MSSP identifier

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        if not self.exists(mssp_id):
            raise MSSPNotFoundError(mssp_id)

        import shutil

        mssp_path = self._mssp_path(mssp_id)
        shutil.rmtree(mssp_path)


class YamlCustomerRepository:
    """YAML-based storage for Customer entities within an MSSP.

    Storage structure:
        {base_path}/{mssp_id}/customers/{customer_id}/customer.yaml
    """

    def __init__(self, base_path: Path, mssp_id: str):
        """Initialize repository.

        Args:
            base_path: Base path for MSSP storage
            mssp_id: MSSP identifier
        """
        self.base_path = base_path
        self.mssp_id = mssp_id
        self._customers_path = base_path / mssp_id / "customers"

    def _customer_path(self, customer_id: str) -> Path:
        """Get path to customer directory."""
        return self._customers_path / customer_id

    def _customer_config_path(self, customer_id: str) -> Path:
        """Get path to customer config file."""
        return self._customer_path(customer_id) / "customer.yaml"

    def exists(self, customer_id: str) -> bool:
        """Check if customer exists."""
        return self._customer_config_path(customer_id).exists()

    def create(self, customer: MSSPCustomer) -> MSSPCustomer:
        """Create a new customer.

        Args:
            customer: Customer entity to create

        Returns:
            Created customer with timestamps

        Raises:
            DuplicateCustomerError: If customer already exists
        """
        if self.exists(customer.customer_id):
            raise DuplicateCustomerError(customer.customer_id, self.mssp_id)

        # Create directory
        customer_path = self._customer_path(customer.customer_id)
        customer_path.mkdir(parents=True, exist_ok=True)

        # Set timestamps
        now = _now_iso()
        data = asdict(customer)
        data["created_at"] = now
        data["updated_at"] = now

        # Convert data_mode enum to string
        data["data_mode"] = customer.data_mode.value

        # Handle webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = (
                asdict(customer.webhook_config) if customer.webhook_config else None
            )

        # Handle SIEM config - convert to dict using its method
        if customer.siem_config is not None:
            data["siem_config"] = customer.siem_config.to_dict()
        else:
            data["siem_config"] = None

        # Write config
        config_path = self._customer_config_path(customer.customer_id)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        return self.get(customer.customer_id)

    def get(self, customer_id: str) -> MSSPCustomer:
        """Get a customer by ID.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer entity

        Raises:
            CustomerNotFoundError: If customer not found
        """
        config_path = self._customer_config_path(customer_id)
        if not config_path.exists():
            raise CustomerNotFoundError(customer_id, self.mssp_id)

        with open(config_path) as f:
            data = yaml.safe_load(f)

        # Convert data_mode string to enum
        data["data_mode"] = DataMode(data["data_mode"])

        # Reconstruct webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = WebhookConfig(**data["webhook_config"])

        # Reconstruct SIEM config
        if data.get("siem_config"):
            from raxe.domain.siem.config import SIEMConfig

            data["siem_config"] = SIEMConfig.from_dict(data["siem_config"])

        return MSSPCustomer(**data)

    def list(self) -> list[MSSPCustomer]:
        """List all customers for this MSSP.

        Returns:
            List of customer entities
        """
        customers = []
        if not self._customers_path.exists():
            return customers

        for customer_dir in self._customers_path.iterdir():
            if customer_dir.is_dir():
                try:
                    customers.append(self.get(customer_dir.name))
                except Exception:  # noqa: S110
                    pass  # Skip invalid entries

        return customers

    def update(self, customer: MSSPCustomer) -> MSSPCustomer:
        """Update an existing customer.

        Args:
            customer: Customer entity with updated values

        Returns:
            Updated customer

        Raises:
            CustomerNotFoundError: If customer not found
        """
        if not self.exists(customer.customer_id):
            raise CustomerNotFoundError(customer.customer_id, self.mssp_id)

        # Get existing for created_at
        existing = self.get(customer.customer_id)

        # Prepare data
        data = asdict(customer)
        data["created_at"] = existing.created_at
        data["updated_at"] = _now_iso()

        # Convert data_mode enum to string
        data["data_mode"] = customer.data_mode.value

        # Handle webhook config
        if data.get("webhook_config"):
            data["webhook_config"] = (
                asdict(customer.webhook_config) if customer.webhook_config else None
            )

        # Handle SIEM config - convert to dict using its method
        if customer.siem_config is not None:
            data["siem_config"] = customer.siem_config.to_dict()
        else:
            data["siem_config"] = None

        # Write config
        config_path = self._customer_config_path(customer.customer_id)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        return self.get(customer.customer_id)

    def delete(self, customer_id: str) -> None:
        """Delete a customer.

        Args:
            customer_id: Customer identifier

        Raises:
            CustomerNotFoundError: If customer not found
        """
        if not self.exists(customer_id):
            raise CustomerNotFoundError(customer_id, self.mssp_id)

        import shutil

        customer_path = self._customer_path(customer_id)
        shutil.rmtree(customer_path)
