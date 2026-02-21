"""Tests for MSSPService customer limit enforcement.

Covers:
- Customer creation within limit succeeds
- Customer creation at limit fails with clear error
- Unlimited (max_customers=0) bypasses limit check
- Tier defaults applied when max_customers not specified
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raxe.application.mssp_service import (
    CreateCustomerRequest,
    CreateMSSPRequest,
    MSSPService,
)
from raxe.domain.mssp.models import (
    MSSP,
    MSSPTier,
)


@pytest.fixture
def tmp_mssp_path(tmp_path: Path) -> Path:
    """Provide a temporary path for MSSP storage."""
    return tmp_path / "mssp_data"


@pytest.fixture
def service(tmp_mssp_path: Path) -> MSSPService:
    """Create an MSSPService with temporary storage."""
    return MSSPService(base_path=tmp_mssp_path)


@pytest.fixture
def starter_mssp(service: MSSPService) -> MSSP:
    """Create a starter-tier MSSP with max_customers=10."""
    return service.create_mssp(
        CreateMSSPRequest(
            mssp_id="mssp_test",
            name="Test MSSP",
            webhook_url="https://example.com/webhook",
            webhook_secret="secret123",
            tier=MSSPTier.STARTER,
            # max_customers=None → uses tier default (10)
        )
    )


class TestCustomerLimitEnforcement:
    """Tests for max_customers enforcement in create_customer()."""

    def test_customer_creation_within_limit(self, service: MSSPService, starter_mssp: MSSP) -> None:
        """Creating a customer within the limit succeeds."""
        customer = service.create_customer(
            CreateCustomerRequest(
                customer_id="cust_001",
                mssp_id="mssp_test",
                name="Customer 1",
            )
        )
        assert customer.customer_id == "cust_001"

    def test_customer_creation_at_limit_fails(
        self, service: MSSPService, starter_mssp: MSSP
    ) -> None:
        """Creating a customer when at the limit raises ValueError."""
        # Create max_customers (10) customers
        for i in range(starter_mssp.max_customers):
            service.create_customer(
                CreateCustomerRequest(
                    customer_id=f"cust_{i:03d}",
                    mssp_id="mssp_test",
                    name=f"Customer {i}",
                )
            )

        # 11th should fail
        with pytest.raises(ValueError, match="Customer limit reached"):
            service.create_customer(
                CreateCustomerRequest(
                    customer_id="cust_overflow",
                    mssp_id="mssp_test",
                    name="Overflow Customer",
                )
            )

    def test_error_message_includes_tier_and_limit(
        self, service: MSSPService, starter_mssp: MSSP
    ) -> None:
        """Error message includes the tier name and limit number."""
        for i in range(starter_mssp.max_customers):
            service.create_customer(
                CreateCustomerRequest(
                    customer_id=f"cust_{i:03d}",
                    mssp_id="mssp_test",
                    name=f"Customer {i}",
                )
            )

        with pytest.raises(ValueError, match=r"10.*starter"):
            service.create_customer(
                CreateCustomerRequest(
                    customer_id="cust_overflow",
                    mssp_id="mssp_test",
                    name="Overflow",
                )
            )

    def test_unlimited_customers_with_zero(self, service: MSSPService) -> None:
        """max_customers=0 means unlimited — no limit enforced."""
        service.create_mssp(
            CreateMSSPRequest(
                mssp_id="mssp_unlimited",
                name="Unlimited MSSP",
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",
                tier=MSSPTier.ENTERPRISE,
                max_customers=0,
            )
        )

        # Should be able to create many customers without hitting a limit
        for i in range(15):
            service.create_customer(
                CreateCustomerRequest(
                    customer_id=f"cust_{i:03d}",
                    mssp_id="mssp_unlimited",
                    name=f"Customer {i}",
                )
            )

        customers = service.list_customers("mssp_unlimited")
        assert len(customers) == 15


class TestTierDefaults:
    """Tests for MSSPTier default_max_customers in CreateMSSPRequest."""

    def test_starter_default_max_customers(self, service: MSSPService) -> None:
        """STARTER tier defaults to 10 max customers."""
        mssp = service.create_mssp(
            CreateMSSPRequest(
                mssp_id="mssp_starter",
                name="Starter",
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",
                tier=MSSPTier.STARTER,
            )
        )
        assert mssp.max_customers == 10

    def test_professional_default_max_customers(self, service: MSSPService) -> None:
        """PROFESSIONAL tier defaults to 50 max customers."""
        mssp = service.create_mssp(
            CreateMSSPRequest(
                mssp_id="mssp_pro",
                name="Professional",
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",
                tier=MSSPTier.PROFESSIONAL,
            )
        )
        assert mssp.max_customers == 50

    def test_enterprise_default_max_customers(self, service: MSSPService) -> None:
        """ENTERPRISE tier defaults to 0 (unlimited) max customers."""
        mssp = service.create_mssp(
            CreateMSSPRequest(
                mssp_id="mssp_ent",
                name="Enterprise",
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",
                tier=MSSPTier.ENTERPRISE,
            )
        )
        assert mssp.max_customers == 0

    def test_explicit_max_customers_overrides_default(self, service: MSSPService) -> None:
        """Explicit max_customers overrides tier default."""
        mssp = service.create_mssp(
            CreateMSSPRequest(
                mssp_id="mssp_custom",
                name="Custom",
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",
                tier=MSSPTier.STARTER,
                max_customers=25,
            )
        )
        assert mssp.max_customers == 25
